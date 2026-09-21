#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path(sys.argv[1])

jev_client = r'''package com.jev.probe.jev

import android.util.Log
import com.jev.probe.core.Analysis
import com.jev.probe.core.ChatSnapshot
import com.jev.probe.core.Choice
import com.jev.probe.core.RankedReply
import com.jev.probe.core.Score
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStream
import java.net.HttpURLConnection
import java.net.URL

/**
 * Direct TypeSafe/Jev client.
 *
 * Judgment and ranking both use TypeSafe's official System One endpoint.
 * Jev does not generate free-form strings, so this private build creates three
 * safe local candidate replies and asks Jev to rank them.
 */
class JevClient(private val key: String, private val replyModel: String) {

    private val decisionsUrl = "https://api.typesafe.ai/v1/systemone"

    fun judge(snapshot: ChatSnapshot, relationship: String): Analysis {
        val start = System.currentTimeMillis()
        try {
            val body = JSONObject()
                .put("model", "jev-latest")
                .put("state", JevQuestions.buildState(snapshot, relationship))
                .put("questions", JevQuestions.judge())
            val answers = postJson(decisionsUrl, body).optJSONObject("answers") ?: JSONObject()
            return Analysis(
                trueIntent = parseChoice(answers.optJSONObject("true_intent")),
                dangerLevel = parseScore(answers.optJSONObject("danger_level")),
                sheNeeds = parseChoice(answers.optJSONObject("she_needs")),
                shouldReplyNow = answers.optJSONObject("should_reply_now")?.optDouble("noul"),
                bestAction = parseChoice(answers.optJSONObject("best_action")),
                tensionResolved = answers.optJSONObject("tension_resolved")?.optDouble("noul"),
                literalQuestion = answers.optJSONObject("literal_question")?.optDouble("noul"),
                rankedReplies = emptyList(),
                latencyMs = System.currentTimeMillis() - start
            )
        } catch (e: Exception) {
            Log.w(TAG, "judge failed: ${e.message}")
            return Analysis(
                null, null, null, null, null, null, null, emptyList(),
                System.currentTimeMillis() - start,
                error = readableError(e)
            )
        }
    }

    fun draftAndRank(snapshot: ChatSnapshot, relationship: String): List<RankedReply> {
        val candidates = generateLocalCandidates(snapshot)
        val questions = JSONObject().put(
            "best_reply",
            JevQuestions.rankQuestion(candidates).getJSONObject("best_reply")
        )
        val body = JSONObject()
            .put("model", "jev-latest")
            .put("state", JevQuestions.buildState(snapshot, relationship))
            .put("questions", questions)
        val answers = postJson(decisionsUrl, body).optJSONObject("answers") ?: JSONObject()
        return parseRanked(answers.optJSONObject("best_reply"), candidates)
    }

    fun analyze(snapshot: ChatSnapshot, relationship: String): Analysis {
        val a = judge(snapshot, relationship)
        if (a.error != null) return a
        val ranked = try {
            draftAndRank(snapshot, relationship)
        } catch (_: Exception) {
            emptyList()
        }
        return a.copy(rankedReplies = ranked)
    }

    /**
     * Jev is a decision model, not a text generator. This private build keeps the
     * app fully usable with a TypeSafe key alone by creating three conservative
     * Chinese candidates locally, then letting Jev rank them against the chat.
     */
    private fun generateLocalCandidates(snapshot: ChatSnapshot): List<String> {
        val latest = snapshot.messages.lastOrNull { it.side == "other" }?.text.orEmpty()
        val lower = latest.lowercase()

        val upset = listOf("生气", "烦", "算了", "失望", "又忘", "不在乎", "别说", "不想听", "呵呵")
            .any { latest.contains(it) }
        val action = listOf("几点", "什么时候", "记得", "发给", "处理", "弄好", "完成", "确认", "安排")
            .any { latest.contains(it) }
        val question = latest.contains("？") || latest.contains("?") ||
            listOf("为什么", "怎么", "什么", "哪", "吗", "呢").any { latest.contains(it) }

        return when {
            upset -> listOf(
                "我看到了，你不舒服的点我会认真处理，不敷衍你。",
                "这件事我先把情况确认清楚，该我处理的我马上处理。",
                "收到，我先不乱解释，把前面的情况弄清楚再认真回复你。"
            )
            action -> listOf(
                "收到，我现在去确认和处理，弄好后第一时间告诉你。",
                "明白，我先把具体时间和细节确认好，再给你准确信息。",
                "好，我记下了。这个我来跟进，有结果马上回你。"
            )
            question || lower.startsWith("why") || lower.startsWith("how") -> listOf(
                "收到，我先把前面的情况确认清楚，再准确回复你。",
                "明白，你问的这个我先核对一下，避免说错。",
                "我看到了，给我一点时间确认，确认好马上告诉你。"
            )
            else -> listOf(
                "收到，我看到了。",
                "明白，我先确认一下具体情况，再回复你。",
                "好，我知道了，这边我会跟进。"
            )
        }
    }

    private fun parseChoice(o: JSONObject?): Choice? {
        o ?: return null
        val probs = HashMap<String, Double>()
        o.optJSONObject("probabilities")?.let { p ->
            p.keys().forEach { k -> probs[k] = p.optDouble(k) }
        }
        return Choice(o.optString("choice"), o.optDouble("confidence", 0.0), probs)
    }

    private fun parseScore(o: JSONObject?): Score? {
        o ?: return null
        val legend = o.optJSONObject("legend")
        val maxLevel = legend?.keys()?.asSequence()?.mapNotNull { it.toIntOrNull() }?.maxOrNull() ?: 9
        return Score(o.optDouble("score", 0.0), o.optDouble("confidence", 0.0), maxLevel)
    }

    private fun parseRanked(o: JSONObject?, candidates: List<String>): List<RankedReply> {
        val keys = listOf("reply_a", "reply_b", "reply_c")
        val probs = o?.optJSONObject("probabilities")
        return candidates.mapIndexed { i, text ->
            RankedReply(text, probs?.optDouble(keys.getOrElse(i) { "" }, 0.0) ?: 0.0)
        }.sortedByDescending { it.prob }
    }

    private fun postJson(urlStr: String, body: JSONObject): JSONObject {
        var attempt = 0
        var lastErr: Exception? = null
        while (attempt < 3) {
            var conn: HttpURLConnection? = null
            try {
                conn = (URL(urlStr).openConnection() as HttpURLConnection).apply {
                    requestMethod = "POST"
                    connectTimeout = 15000
                    readTimeout = 25000
                    doOutput = true
                    setRequestProperty("Authorization", "Bearer $key")
                    setRequestProperty("Content-Type", "application/json")
                }
                val bytes = body.toString().toByteArray(Charsets.UTF_8)
                conn.outputStream.use { os: OutputStream -> os.write(bytes) }
                val code = conn.responseCode
                if (code == 429 || code == 529) {
                    attempt++
                    Thread.sleep(500L * (1L shl attempt))
                    continue
                }
                val stream = if (code in 200..299) conn.inputStream else conn.errorStream
                val text = BufferedReader(InputStreamReader(stream, Charsets.UTF_8)).use { it.readText() }
                if (code !in 200..299) throw RuntimeException("HTTP $code: ${text.take(220)}")
                return JSONObject(text)
            } catch (e: Exception) {
                lastErr = e
                if (e.message?.contains("HTTP 4") == true) throw e
                attempt++
                if (attempt < 3) Thread.sleep(500L * (1L shl attempt))
            } finally {
                conn?.disconnect()
            }
        }
        throw lastErr ?: RuntimeException("request failed")
    }

    private fun readableError(e: Exception): String {
        val m = e.message ?: e.javaClass.simpleName
        return when {
            m.contains("HTTP 401") -> "TypeSafe/Jev 密钥无效（401）"
            m.contains("HTTP 422") -> "Jev 请求格式错误（422）：${m.take(180)}"
            m.contains("HTTP 429") -> "Jev 请求过快，请稍后再试"
            m.contains("HTTP 529") -> "Jev 服务繁忙，请稍后再试"
            m.contains("HTTP 4") -> "请求被拒：$m"
            m.contains("timed out") || m.contains("timeout") -> "网络超时，请检查连接"
            m.contains("Unable to resolve host") || m.contains("Failed to connect") -> "无法连接网络"
            else -> "分析失败：$m"
        }
    }

    companion object { private const val TAG = "JEVASSIST" }
}
'''

prefs = r'''package com.jev.probe.core

import android.content.Context

/**
 * App-private config store.
 *
 * This build can bootstrap the TypeSafe/Jev API key from a private APK asset.
 * If the user saves another key in Settings, the saved key takes precedence.
 */
class Prefs(private val context: Context) {

    private val sp = context.getSharedPreferences("jev_assistant", Context.MODE_PRIVATE)

    private fun bundledKey(): String {
        val raw = runCatching {
            context.assets.open("bootstrap_key.txt").bufferedReader().use { it.readText().trim() }
        }.getOrDefault("")
        return if (raw.isBlank() || raw.startsWith("__TYPESAFE_KEY_")) "" else raw
    }

    // Kept under the old property name to minimize changes elsewhere in the app.
    var openRouterKey: String
        get() = (sp.getString(K_KEY, "") ?: "").ifBlank { bundledKey() }
        set(v) = sp.edit().putString(K_KEY, v.trim()).apply()

    /** Unused by the direct-TypeSafe private build; retained for config compatibility. */
    var replyModel: String
        get() = sp.getString(K_REPLY_MODEL, DEFAULT_REPLY_MODEL) ?: DEFAULT_REPLY_MODEL
        set(v) = sp.edit().putString(K_REPLY_MODEL, v.trim()).apply()

    var relationship: String
        get() = sp.getString(K_REL, DEFAULT_REL) ?: DEFAULT_REL
        set(v) = sp.edit().putString(K_REL, v).apply()

    var enabled: Boolean
        get() = sp.getBoolean(K_ENABLED, true)
        set(v) = sp.edit().putBoolean(K_ENABLED, v).apply()

    var whitelist: Set<String>
        get() = sp.getStringSet(K_WHITELIST, emptySet()) ?: emptySet()
        set(v) = sp.edit().putStringSet(K_WHITELIST, v).apply()

    var overlayOpacity: Int
        get() = sp.getInt(K_OPACITY, 92).coerceIn(60, 100)
        set(v) = sp.edit().putInt(K_OPACITY, v.coerceIn(60, 100)).apply()

    var bubbleY: Int
        get() = sp.getInt(K_BUBBLE_Y, -1)
        set(v) = sp.edit().putInt(K_BUBBLE_Y, v).apply()

    var bubbleX: Int
        get() = sp.getInt(K_BUBBLE_X, -1)
        set(v) = sp.edit().putInt(K_BUBBLE_X, v).apply()

    var autoAnalyze: Boolean
        get() = sp.getBoolean(K_AUTO, true)
        set(v) = sp.edit().putBoolean(K_AUTO, v).apply()

    fun isAllowed(title: String?): Boolean {
        val wl = whitelist
        if (wl.isEmpty()) return true
        if (title == null) return false
        return wl.any { title.contains(it) }
    }

    fun hasKey(): Boolean = openRouterKey.isNotBlank()

    companion object {
        private const val K_KEY = "typesafe_key"
        private const val K_REPLY_MODEL = "reply_model"
        private const val K_REL = "relationship"
        private const val K_ENABLED = "enabled"
        private const val K_WHITELIST = "whitelist"
        private const val K_OPACITY = "overlay_opacity"
        private const val K_BUBBLE_Y = "bubble_y"
        private const val K_BUBBLE_X = "bubble_x"
        private const val K_AUTO = "auto_analyze"

        const val DEFAULT_REPLY_MODEL = "local-templates+jev"
        const val DEFAULT_REL = "对方是我的伴侣；from=me 的是我发的，from=other 的是对方发的"
    }
}
'''

(root / "app/src/main/java/com/jev/probe/jev/JevClient.kt").write_text(jev_client, encoding="utf-8")
(root / "app/src/main/java/com/jev/probe/core/Prefs.kt").write_text(prefs, encoding="utf-8")

settings_path = root / "app/src/main/java/com/jev/probe/SettingsActivity.kt"
s = settings_path.read_text(encoding="utf-8")
s = s.replace('label("OpenRouter 密钥")', 'label("TypeSafe / Jev 密钥")')
s = s.replace('"sk-or-v1-..."', '"apikey_..."')
s = s.replace('label("回复生成模型")', 'label("回复方式（此安装包）")')
s = s.replace(
    'val modelEdit = edit(prefs.replyModel, Prefs.DEFAULT_REPLY_MODEL)\n        card1.addView(modelEdit)',
    'val modelEdit = edit("本地候选 + Jev 排序", "本地候选 + Jev 排序").apply { isEnabled = false }\n        card1.addView(modelEdit)'
)
s = s.replace(
    'InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD',
    'InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD'
)
settings_path.write_text(s, encoding="utf-8")

service_path = root / "app/src/main/java/com/jev/probe/capture/ChatCaptureService.kt"
s = service_path.read_text(encoding="utf-8")
s = s.replace("未设置 OpenRouter 密钥，去设置里填", "未设置 TypeSafe/Jev 密钥，去设置里填")
service_path.write_text(s, encoding="utf-8")

assets = root / "app/src/main/assets"
assets.mkdir(parents=True, exist_ok=True)
(assets / "bootstrap_key.txt").write_text("__TYPESAFE_KEY_PLACEHOLDER__\n", encoding="utf-8")

# Build label so it is obvious this is the direct-TypeSafe private build.
strings_path = root / "app/src/main/res/values/strings.xml"
ss = strings_path.read_text(encoding="utf-8")
ss = ss.replace("Jev 聊天助手", "Jev 聊天助手 · Direct")
strings_path.write_text(ss, encoding="utf-8")

print("Patched Jev project for direct TypeSafe API.")

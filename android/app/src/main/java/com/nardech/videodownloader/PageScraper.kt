package com.nardech.videodownloader

import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.IOException
import java.net.URI
import java.nio.charset.Charset
import java.util.concurrent.TimeUnit

/**
 * โหมดสำรองสำหรับหน้าเว็บที่เอนจิน yt-dlp อ่านไม่ได้ (เช่นหน้า player ที่ฝังด้วย JS)
 * — พอร์ตจาก html_media.py ของแอปเดสก์ท็อป: หาลิงก์สื่อจาก attribute ทั่วไป/ขี้เกียจโหลด
 * (data-src ฯลฯ), URL ที่ฝังใน JSON/สคริปต์ (รวมแบบ escape \/ และ \u0026)
 * และ iframe player — ลำดับ: ไฟล์ตรง → manifest (.m3u8/.mpd) → iframe
 * (ดึง manifest ด้วยเอนจิน yt-dlp ต่อ; ไม่ hardcode โดเมนใดๆ)
 */
object PageScraper {

    private val MEDIA_EXT = setOf(
        "mp4", "webm", "mkv", "mov", "m4v", "flv", "ts", "avi",
        "mp3", "m4a", "ogg", "wav", "aac", "opus", "ogv", "3gp", "m3u8", "mpd",
    )
    private val MANIFEST_EXT = setOf("m3u8", "mpd")

    private val ATTR = Regex(
        """(?:src|href|content|data-src|data-video-src|data-mp4|data-hls|data-file|data-url|data-video|data-source)\s*=\s*["']([^"']+)["']""",
        RegexOption.IGNORE_CASE,
    )
    private val QUOTED = Regex(
        """["']([^"'\s]+?\.(?:mp4|m3u8|mpd|webm|mkv|mov|m4v|ts|flv|mp3|m4a|aac|ogg|opus|ogv|3gp)(?:\?[^\s"']*)?)["']""",
        RegexOption.IGNORE_CASE,
    )
    private val IFRAME = Regex(
        """<iframe[^>]*?(?:\bsrc|data-src)\s*=\s*["']([^"']+)["']""",
        RegexOption.IGNORE_CASE,
    )
    private val TITLE = Regex(
        """<title[^>]*>(.*?)</title>""",
        setOf(RegexOption.IGNORE_CASE, RegexOption.DOT_MATCHES_ALL),
    )

    private const val UA =
        "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36"
    private val SKIP_PREFIX = listOf("#", "javascript:", "data:", "blob:", "about:", "mailto:")

    private val client by lazy {
        OkHttpClient.Builder()
            .connectTimeout(20, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .build()
    }

    data class Result(
        val title: String?,
        val direct: List<String>,
        val manifests: List<String>,
        val iframes: List<String>,
    ) {
        val candidates: List<String> get() = direct + manifests + iframes
    }

    fun extOf(url: String): String =
        url.substringBefore('?').substringBefore('#').substringAfterLast('.', "").lowercase()

    fun isDirectMedia(url: String): Boolean = extOf(url) in MEDIA_EXT && extOf(url) !in MANIFEST_EXT

    private fun unescape(s: String): String =
        s.replace("\\/", "/").replace("\\u0026", "&").replace("\\u002F", "&")

    private fun absolutize(ref: String, baseUrl: String): String? {
        val lower = ref.lowercase()
        if (lower.startsWith("http://") || lower.startsWith("https://")) return ref
        if (lower.startsWith("//")) return "https:$ref"
        if (ref.startsWith("/") || ref.startsWith("./") || ref.contains('/')) {
            return try {
                URI(baseUrl).resolve(ref.replace(" ", "%20")).toString()
            } catch (_: Exception) {
                null
            }
        }
        return null // ชื่อไฟล์เปล่าๆ เสี่ยง false positive
    }

    /** แยกลิงก์สื่อจากเนื้อหา HTML — เทสต์ JVM ได้โดยไม่ต้องมีเครือข่าย */
    fun extract(html: String, baseUrl: String): Result {
        val found = linkedSetOf<String>()
        val manifests = linkedSetOf<String>()

        fun addCandidate(raw: String) {
            val ref = unescape(raw.trim())
            if (ref.isEmpty() || SKIP_PREFIX.any { ref.lowercase().startsWith(it) }) return
            val ext = extOf(ref)
            if (ext !in MEDIA_EXT) return
            val abs = absolutize(ref, baseUrl) ?: return
            if (ext in MANIFEST_EXT) manifests.add(abs) else found.add(abs)
        }

        for (m in ATTR.findAll(html)) addCandidate(m.groupValues[1])
        // สื่อที่ฝังใน JSON/สคริปต์ (player config, JSON-LD) — ตัดชื่อไฟล์เปล่าๆ ที่ไม่มี "/" ทิ้ง
        for (m in QUOTED.findAll(html)) {
            val ref = m.groupValues[1]
            if (ref.contains('/') || ref.lowercase().startsWith("http")) addCandidate(ref)
        }

        val iframes = linkedSetOf<String>()
        for (m in IFRAME.findAll(html)) {
            val ref = unescape(m.groupValues[1].trim())
            if (ref.isEmpty() || SKIP_PREFIX.any { ref.lowercase().startsWith(it) }) continue
            absolutize(ref, baseUrl)?.let { if (it != baseUrl) iframes.add(it) }
        }

        val title = TITLE.find(html)?.groupValues?.get(1)
            ?.replace(Regex("\\s+"), " ")?.trim()?.take(150)

        return Result(
            title = title,
            direct = found.toList(),
            manifests = manifests.toList(),
            iframes = iframes.toList().take(5),
        )
    }

    /** ดึงหน้าเว็บ (decode ตาม charset จริง รองรับเว็บไทย windows-874) */
    fun fetch(url: String, referer: String? = null): String {
        val rb = Request.Builder().url(url).header("User-Agent", UA)
        if (referer != null) rb.header("Referer", referer)
        client.newCall(rb.build()).execute().use { resp ->
            if (!resp.isSuccessful) throw IOException("HTTP ${resp.code}")
            val bytes = resp.body?.bytes() ?: throw IOException("empty body")
            val headerCharset = resp.header("Content-Type")
                ?.split(";")?.firstOrNull { it.trim().startsWith("charset=", true) }
                ?.substringAfter('=')?.trim()?.removeSurrounding("\"")
            val charset = detectCharset(bytes, headerCharset)
            return String(bytes, charset)
        }
    }

    private fun detectCharset(bytes: ByteArray, headerCharset: String?): Charset {
        val name = headerCharset ?: run {
            val head = String(bytes, 0, minOf(bytes.size, 8192), Charsets.ISO_8859_1)
            Regex("""<meta[^>]+charset=["']?([\w-]+)""", RegexOption.IGNORE_CASE)
                .find(head)?.groupValues?.get(1)
        } ?: return Charsets.UTF_8
        return runCatching { Charset.forName(name) }.getOrDefault(Charsets.UTF_8)
    }
}

package com.nardech.videodownloader

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * เทสต์ JVM ของ PageScraper (โหมดสำรองแยกสื่อจากหน้าเว็บ) — ไม่ใช้เครือข่าย
 * รูปแบบครอบคลุมเว็บจริง: lazy-load data-*, สื่อใน JSON (escape \/ และ \u0026),
 * manifest .m3u8/.mpd ในสคริปต์ และ iframe player
 */
class PageScraperTest {

    private val page = """
        <html><head>
        <title>ทดสอบ หน้าเว็บ</title>
        <meta property="og:video:secure_url" content="https://cdn.example.com/meta/secure.mp4">
        </head><body>
        <div class="wp-video" data-src="https://cdn.example.com/lazy/div.mp4"></div>
        <video controls><source data-video-src="https://cdn.example.com/lazy/source.mp4" type="video/mp4"></video>
        <iframe data-src="https://player.example.com/e/abc/player.html"></iframe>
        <script>
        var cfg = {"file":"https:\/\/cdn.example.com\/json\/escaped.mp4?tok=1\u0026sig=2"};
        var hls = 'https://cdn.example.com/hls/index.m3u8';
        var dash = '/media/episode-1/output.mpd';
        var bare = "movie.mp4";
        </script>
        </body></html>
    """.trimIndent()

    private val base = "https://site.example/watch/1/"

    @Test
    fun `lazy load attributes are found`() {
        val r = PageScraper.extract(page, base)
        assertTrue(r.direct.contains("https://cdn.example.com/lazy/div.mp4"))
        assertTrue(r.direct.contains("https://cdn.example.com/lazy/source.mp4"))
        assertTrue(r.direct.contains("https://cdn.example.com/meta/secure.mp4"))
    }

    @Test
    fun `json escaped urls are unescaped`() {
        val r = PageScraper.extract(page, base)
        assertTrue(r.direct.contains("https://cdn.example.com/json/escaped.mp4?tok=1&sig=2"))
    }

    @Test
    fun `manifests are separated from progressive files`() {
        val r = PageScraper.extract(page, base)
        assertTrue(r.manifests.contains("https://cdn.example.com/hls/index.m3u8"))
        assertTrue(r.manifests.contains("https://site.example/media/episode-1/output.mpd"))
        assertFalse(r.direct.any { it.endsWith(".m3u8") || it.endsWith(".mpd") })
    }

    @Test
    fun `iframes are collected and absolutized`() {
        val r = PageScraper.extract(page, base)
        assertTrue(r.iframes.contains("https://player.example.com/e/abc/player.html"))
    }

    @Test
    fun `bare filenames without slash are ignored`() {
        val r = PageScraper.extract(page, base)
        assertFalse(r.candidates.any { it.endsWith("/movie.mp4") || it == "movie.mp4" })
    }

    @Test
    fun `no duplicates`() {
        val r = PageScraper.extract(page, base)
        assertEquals(r.candidates.size, r.candidates.toSet().size)
    }

    @Test
    fun `title is extracted`() {
        val r = PageScraper.extract(page, base)
        assertEquals("ทดสอบ หน้าเว็บ", r.title)
    }

    @Test
    fun `candidates order is direct then manifest then iframe`() {
        val r = PageScraper.extract(page, base)
        val iLastDirect = r.candidates.lastIndexOf(r.direct.last())
        val iFirstManifest = r.candidates.indexOf(r.manifests.first())
        val iFirstIframe = r.candidates.indexOf(r.iframes.first())
        assertTrue(iLastDirect < iFirstManifest)
        assertTrue(iFirstManifest < iFirstIframe)
    }

    @Test
    fun `direct media url detection`() {
        assertTrue(PageScraper.isDirectMedia("https://a.b/c/clip.mp4?tok=1"))
        assertFalse(PageScraper.isDirectMedia("https://a.b/c/index.m3u8"))
        assertFalse(PageScraper.isDirectMedia("https://a.b/page.html"))
    }

    @Test
    fun `player html pattern from real world is matched`() {
        // รูปแบบเดียวกับ player ฝังวีดีโอจริง: dash.js + inline script ระบุ .mpd
        val playerPage = """
            <html><head><title>Player</title>
            <script src="https://cdn.dashjs.org/latest/dash.all.min.js"></script></head>
            <body><div id="videoPlayer"></div>
            <script>var player = dashjs.MediaPlayer().create();
            player.initialize(document.querySelector("#videoPlayer"), "https://host.example/xyz/output.mpd", true);</script>
            </body></html>
        """.trimIndent()
        val r = PageScraper.extract(playerPage, "https://host.example/xyz/player.html")
        assertTrue(r.manifests.contains("https://host.example/xyz/output.mpd"))
    }
}

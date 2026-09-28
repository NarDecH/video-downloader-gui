package com.nardech.videodownloader

import android.Manifest
import android.app.DownloadManager
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.view.View
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.Spinner
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.schabi.newpipe.extractor.NewPipe
import org.schabi.newpipe.extractor.ServiceList
import org.schabi.newpipe.extractor.stream.StreamInfo
import org.schabi.newpipe.extractor.stream.VideoStream
import org.schabi.newpipe.extractor.downloader.Downloader
import org.schabi.newpipe.extractor.downloader.Request
import org.schabi.newpipe.extractor.downloader.Response
import org.schabi.newpipe.extractor.exceptions.ReCaptchaException
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import java.util.concurrent.TimeUnit

class MainActivity : AppCompatActivity() {

    private lateinit var etUrl: TextView
    private lateinit var btnFetch: Button
    private lateinit var btnDownload: Button
    private lateinit var cardInfo: LinearLayout
    private lateinit var tvTitle: TextView
    private lateinit var tvMeta: TextView
    private lateinit var spQuality: Spinner
    private lateinit var progress: ProgressBar
    private lateinit var tvStatus: TextView

    private var streamInfo: StreamInfo? = null
    private var videoStreams: List<VideoStream> = emptyList()
    private var currentDownloadId: Long = -1

    private val downloaderImpl = object : Downloader() {
        private val client = okhttp3.OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .build()

        override fun execute(request: Request): Response {
            val body = request.dataToSend()
            val method = request.httpMethod()
            val rb = okhttp3.Request.Builder()
                .url(request.url())
                .method(
                    method,
                    if (body != null)
                        okhttp3.RequestBody.create(
                            "application/json".toMediaTypeOrNull(), body
                        )
                    else if (method.equals("POST", true) || method.equals("PUT", true) || method.equals("PATCH", true))
                        okhttp3.RequestBody.create(null, ByteArray(0))
                    else null
                )
            request.headers().forEach { (k, v) -> rb.header(k, v.joinToString(", ")) }
            client.newCall(rb.build()).execute().use { resp ->
                val b = resp.body?.string() ?: ""
                val latestUrl = resp.request.url.toString()
                return Response(resp.code, resp.message, resp.headers.toMultimap(), b, latestUrl)
            }
        }

        @Throws(ReCaptchaException::class)
        override fun get(url: String): Response = execute(Request.Builder().url(url).build())
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        etUrl = findViewById(R.id.etUrl)
        btnFetch = findViewById(R.id.btnFetch)
        btnDownload = findViewById(R.id.btnDownload)
        cardInfo = findViewById(R.id.cardInfo)
        tvTitle = findViewById(R.id.tvTitle)
        tvMeta = findViewById(R.id.tvMeta)
        spQuality = findViewById(R.id.spQuality)
        progress = findViewById(R.id.progress)
        tvStatus = findViewById(R.id.tvStatus)

        NewPipe.init(downloaderImpl)

        // รับลิงก์จากการแชร์ (ACTION_SEND)
        val shared = if (intent?.action == android.content.Intent.ACTION_SEND) {
            intent.getStringExtra(android.content.Intent.EXTRA_TEXT)
        } else null
        if (!shared.isNullOrBlank()) {
            etUrl.text = shared
            fetchInfo()
        }

        btnFetch.setOnClickListener { fetchInfo() }
        btnDownload.setOnClickListener { startDownload() }

        // ขอสิทธิ์ notification สำหรับ Android 13+
        if (Build.VERSION.SDK_INT >= 33) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED
            ) {
                ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
            }
        }
    }

    private fun fetchInfo() {
        val url = etUrl.text?.toString()?.trim().orEmpty()
        if (url.isEmpty()) {
            Toast.makeText(this, "กรุณาวางลิงก์วีดีโอ", Toast.LENGTH_SHORT).show()
            return
        }
        btnFetch.isEnabled = false
        tvStatus.text = getString(R.string.fetching)
        tvStatus.visibility = View.VISIBLE
        cardInfo.visibility = View.GONE
        btnDownload.visibility = View.GONE
        spQuality.visibility = View.GONE

        CoroutineScope(Dispatchers.IO).launch {
            try {
                val info = StreamInfo.getInfo(ServiceList.YouTube, url)
                streamInfo = info
                val streams = info.videoStreams.filter { it.url != null && !it.isVideoOnly }
                    .sortedByDescending { it.height }
                videoStreams = streams
                withContext(Dispatchers.Main) {
                    tvTitle.text = info.name
                    tvMeta.text = "${info.uploaderName} • ${info.duration / 60} นาที • รองรับ ${streams.size} คุณภาพ"
                    cardInfo.visibility = View.VISIBLE
                    if (streams.isNotEmpty()) {
                        val labels = streams.map { s ->
                            val fps = if (s.fps > 45) "${s.fps}fps" else ""
                            "${s.resolution} ${s.format?.name ?: ""} $fps".trim()
                        }
                        spQuality.adapter = ArrayAdapter(
                            this@MainActivity, android.R.layout.simple_spinner_dropdown_item, labels
                        )
                        spQuality.visibility = View.VISIBLE
                        btnDownload.visibility = View.VISIBLE
                    } else {
                        tvStatus.text = "ไม่พบสตรีมวิดีโอที่ดาวน์โหลดได้"
                        return@withContext
                    }
                    tvStatus.text = ""
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    tvStatus.text = getString(R.string.error_generic, e.message ?: e.javaClass.simpleName)
                }
            } finally {
                withContext(Dispatchers.Main) { btnFetch.isEnabled = true }
            }
        }
    }

    private fun startDownload() {
        val stream = videoStreams.getOrNull(spQuality.selectedItemPosition) ?: return
        val info = streamInfo ?: return
        btnDownload.isEnabled = false

        // Android 9 ลงไปต้องขอ WRITE_EXTERNAL_STORAGE
        if (Build.VERSION.SDK_INT <= 28 &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.WRITE_EXTERNAL_STORAGE)
            != PackageManager.PERMISSION_GRANTED
        ) {
            ActivityCompat.requestPermissions(
                this, arrayOf(Manifest.permission.WRITE_EXTERNAL_STORAGE), 2
            )
            btnDownload.isEnabled = true
            return
        }

        val safeName = info.name.replace(Regex("[\\\\/:*?\"<>|]+"), "_").take(120)
        val fileName = "$safeName.${stream.format?.suffix ?: "mp4"}"

        val request = DownloadManager.Request(Uri.parse(stream.url)).apply {
            setTitle(fileName)
            setDescription("Video Downloader GUI")
            setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
            setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, fileName)
            setAllowedOverMetered(true)
        }
        val dm = getSystemService(DOWNLOAD_SERVICE) as DownloadManager
        currentDownloadId = dm.enqueue(request)

        progress.visibility = View.VISIBLE
        tvStatus.text = getString(R.string.downloading)
        Toast.makeText(this, "เริ่มดาวน์โหลด: $fileName", Toast.LENGTH_SHORT).show()

        // ติดตามความคืบหน้า
        CoroutineScope(Dispatchers.IO).launch {
            while (currentDownloadId >= 0) {
                val q = dm.query(DownloadManager.Query().setFilterById(currentDownloadId))
                if (q.moveToFirst()) {
                    val done = q.getInt(q.getColumnIndexOrThrow(DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR))
                    val total = q.getInt(q.getColumnIndexOrThrow(DownloadManager.COLUMN_TOTAL_SIZE_BYTES))
                    val status = q.getInt(q.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS))
                    val pct = if (total > 0) done * 100 / total else 0
                    withContext(Dispatchers.Main) {
                        progress.progress = pct
                        when (status) {
                            DownloadManager.STATUS_SUCCESSFUL -> {
                                tvStatus.text = getString(R.string.done)
                                progress.visibility = View.GONE
                                btnDownload.isEnabled = true
                                currentDownloadId = -1
                            }
                            DownloadManager.STATUS_FAILED -> {
                                tvStatus.text = "ดาวน์โหลดล้มเหลว"
                                btnDownload.isEnabled = true
                                currentDownloadId = -1
                            }
                            else -> tvStatus.text = "กำลังดาวน์โหลด… $pct%"
                        }
                    }
                    if (status == DownloadManager.STATUS_SUCCESSFUL || status == DownloadManager.STATUS_FAILED) break
                }
                Thread.sleep(800)
            }
        }
    }

    companion object {
        const val IntentExtraShareKey = "shared_url"
    }

    private fun okHttpClientForTest() = okhttp3.OkHttpClient()
}

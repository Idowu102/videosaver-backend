package com.idchest.videosaverapp

import android.content.ContentValues
import android.content.Intent
import android.net.Uri
import android.os.*
import android.provider.MediaStore
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import com.bumptech.glide.Glide
import com.google.android.gms.ads.*
import com.google.android.gms.ads.interstitial.InterstitialAd
import com.google.android.gms.ads.interstitial.InterstitialAdLoadCallback
import okhttp3.*
import org.json.JSONObject
import java.io.IOException
import java.net.URLEncoder
import java.util.concurrent.TimeUnit

class MainActivity : AppCompatActivity() {

    private val client = OkHttpClient.Builder()
        .connectTimeout(60, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .writeTimeout(60, TimeUnit.SECONDS)
        .build()

    private lateinit var input: EditText
    private lateinit var titleText: TextView
    private lateinit var progressBar: ProgressBar
    private lateinit var progressText: TextView
    private lateinit var thumb: ImageView

    private var downloadUrl = ""
    private var audioUrl = ""
    private var title = ""

    private var interstitialAd: InterstitialAd? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        MobileAds.initialize(this)
        loadInterstitialAd()

        input = findViewById(R.id.urlInput)
        titleText = findViewById(R.id.titleText)
        progressBar = findViewById(R.id.progressBar)
        progressText = findViewById(R.id.progressText)
        thumb = findViewById(R.id.thumbImage)

        findViewById<Button>(R.id.fetchBtn).setOnClickListener {
            val url = input.text.toString().trim()
            if (url.isEmpty()) {
                Toast.makeText(this, "Paste URL", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }

            fetchVideo(url)
            fetchAudio(url)
            showAd()
        }

        findViewById<Button>(R.id.downloadBtn).setOnClickListener {
            if (downloadUrl.isNotEmpty()) {
                downloadFile(downloadUrl, "$title.mp4")
                showAd()
            } else {
                Toast.makeText(this, "Fetch first", Toast.LENGTH_SHORT).show()
            }
        }

        findViewById<Button>(R.id.audioBtn).setOnClickListener {
            if (audioUrl.isNotEmpty()) {
                downloadFile(audioUrl, "$title.mp3")
                showAd()
            } else {
                Toast.makeText(this, "Fetch first", Toast.LENGTH_SHORT).show()
            }
        }
    }

    // ================= ADS =================

    private fun loadInterstitialAd() {
        InterstitialAd.load(
            this,
            "ca-app-pub-5425962691180386/1619020807",
            AdRequest.Builder().build(),
            object : InterstitialAdLoadCallback() {
                override fun onAdLoaded(ad: InterstitialAd) {
                    interstitialAd = ad
                }

                override fun onAdFailedToLoad(error: LoadAdError) {
                    interstitialAd = null
                }
            }
        )
    }

    private fun showAd() {
        interstitialAd?.show(this)
        interstitialAd = null
        loadInterstitialAd()
    }

    // ================= FETCH VIDEO =================

    private fun fetchVideo(url: String) {
        val encoded = URLEncoder.encode(url, "UTF-8")

        val request = Request.Builder()
            .url("https://videosaver-backend-production.up.railway.app/stream?url=$encoded")
            .build()

        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                runOnUiThread {
                    Toast.makeText(this@MainActivity, "Fetch failed", Toast.LENGTH_SHORT).show()
                }
            }

            override fun onResponse(call: Call, response: Response) {
                val body = response.body?.string()

                runOnUiThread {
                    try {
                        val json = JSONObject(body ?: "{}")

                        if (json.optString("status") != "success") {
                            Toast.makeText(this@MainActivity, "Failed to fetch", Toast.LENGTH_SHORT).show()
                            return@runOnUiThread
                        }

                        title = json.optString("title")
                        downloadUrl = json.optString("stream_url")

                        titleText.text = title

                        Glide.with(this@MainActivity)
                            .load(json.optString("thumbnail"))
                            .into(thumb)

                    } catch (e: Exception) {
                        Toast.makeText(this@MainActivity, "Parse error", Toast.LENGTH_SHORT).show()
                    }
                }
            }
        })
    }

    // ================= FETCH AUDIO =================

    private fun fetchAudio(url: String) {
        val encoded = URLEncoder.encode(url, "UTF-8")

        val request = Request.Builder()
            .url("https://videosaver-backend-production.up.railway.app/audio?url=$encoded")
            .build()

        client.newCall(request).enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {}

            override fun onResponse(call: Call, response: Response) {
                val body = response.body?.string()

                runOnUiThread {
                    try {
                        val json = JSONObject(body ?: "{}")
                        audioUrl = json.optString("audio_url")
                    } catch (_: Exception) {}
                }
            }
        })
    }

    // ================= DOWNLOAD FIXED =================

    private fun downloadFile(url: String, fileName: String) {

        progressBar.progress = 0
        progressText.text = "0%"

        Thread {

            try {
                val request = Request.Builder().url(url).build()
                val response = client.newCall(request).execute()

                if (!response.isSuccessful) {
                    runOnUiThread {
                        Toast.makeText(this, "Download failed", Toast.LENGTH_LONG).show()
                    }
                    return@Thread
                }

                val body = response.body ?: return@Thread
                val inputStream = body.byteStream()

                val resolver = contentResolver

                val values = ContentValues().apply {
                    put(MediaStore.MediaColumns.DISPLAY_NAME, fileName)
                    put(
                        MediaStore.MediaColumns.MIME_TYPE,
                        if (fileName.endsWith(".mp3")) "audio/mpeg" else "video/mp4"
                    )
                    put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS)
                }

                val uri = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    MediaStore.Downloads.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY)
                } else {
                    MediaStore.Files.getContentUri("external")
                }

                val fileUri = resolver.insert(uri, values)

                if (fileUri == null) {
                    runOnUiThread {
                        Toast.makeText(this, "Storage error", Toast.LENGTH_LONG).show()
                    }
                    return@Thread
                }

                val outputStream = resolver.openOutputStream(fileUri)

                if (outputStream == null) {
                    runOnUiThread {
                        Toast.makeText(this, "Output error", Toast.LENGTH_LONG).show()
                    }
                    return@Thread
                }

                val buffer = ByteArray(8192)
                var read: Int

                while (inputStream.read(buffer).also { read = it } != -1) {
                    outputStream.write(buffer, 0, read)
                }

                outputStream.flush()
                outputStream.close()
                inputStream.close()

                runOnUiThread {
                    progressBar.progress = 100
                    progressText.text = "100%"

                    Toast.makeText(this, "Download complete", Toast.LENGTH_LONG).show()

                    val intent = Intent(Intent.ACTION_VIEW).apply {
                        setDataAndType(fileUri, if (fileName.endsWith(".mp3")) "audio/*" else "video/*")
                        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    }

                    startActivity(intent)
                }

            } catch (e: Exception) {
                runOnUiThread {
                    Toast.makeText(this, "Error: ${e.message}", Toast.LENGTH_LONG).show()
                }
            }

        }.start()
    }
}

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

import java.util.Base64

android {
    namespace = "com.nardech.videodownloader"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.nardech.videodownloader"
        minSdk = 24
        targetSdk = 34
        versionCode = 3
        versionName = "1.2.0"
        // เอนจิน yt-dlp/ffmpeg แพ็ก .so ตาม ABI — ตัด x86 (32-bit emulator) ทิ้งเพื่อคุมขนาด APK
        ndk {
            abiFilters += listOf("arm64-v8a", "armeabi-v7a", "x86_64")
        }
    }

    signingConfigs {
        create("release") {
            // CI อ่านจาก secret (base64), local ใช้ keystore ในเครื่อง
            val ksB64 = System.getenv("ANDROID_KEYSTORE_B64")
            if (ksB64 != null) {
                val tmp = File.createTempFile("vdlks", ".jks")
                tmp.writeBytes(Base64.getDecoder().decode(ksB64))
                storeFile = tmp
            } else {
                storeFile = file("../keystore/release.jks")
            }
            storePassword = System.getenv("ANDROID_KEYSTORE_PASSWORD") ?: "videodownler2026"
            keyAlias = System.getenv("ANDROID_KEY_ALIAS") ?: "vdl"
            keyPassword = System.getenv("ANDROID_KEY_PASSWORD") ?: "videodownler2026"
        }
    }
    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            signingConfig = signingConfigs.getByName("release")
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    packaging {
        resources.excludes += "META-INF/*"
    }
}

dependencies {
    // NewPipeExtractor: แยกลิงก์สตรีมจาก YouTube ฯลฯ (MIT)
    implementation("com.github.TeamNewPipe:NewPipeExtractor:v0.24.6")
    // OkHttp: HTTP client ที่ NewPipeExtractor ใช้ + ใช้ดาวน์โหลดเอง
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    // เอนจิน yt-dlp + ffmpeg จริงบน Android (Python runtime + ffmpeg แพ็กใน .so)
    // — รองรับลิงก์ทั่วไป/หลายพันเว็บไซต์, HLS/DASH และการรวมไฟล์ video+audio
    implementation("io.github.junkfood02.youtubedl-android:library:0.18.1")
    implementation("io.github.junkfood02.youtubedl-android:ffmpeg:0.18.1")
    // ส่วน UI พื้นฐาน
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("com.google.android.material:material:1.12.0")
    implementation("androidx.constraintlayout:constraintlayout:2.1.4")
    // ดาวน์โหลดเข้า MediaStore อย่างถูกต้องบน Android 10+
    implementation("androidx.documentfile:documentfile:1.0.1")
    // Coroutine สำหรับงานเบื้องหลัง
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")

    testImplementation("junit:junit:4.13.2")
}

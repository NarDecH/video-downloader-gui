# NewPipeExtractor uses nanojson + jsoup; keep them from being stripped
-keep class org.nanojson.** { *; }
-keep class org.jsoup.** { *; }
-keep class org.schabi.newpipe.extractor.** { *; }
-dontwarn org.mozilla.javascript.**
-dontwarn org.mozilla.classfile.**
-dontwarn org.jspecify.annotations.NullMarked

# youtubedl-android (Python/yt-dlp runtime wrapper) + commons-compress ที่ไลบรารีใช้
-keep class com.yausername.** { *; }
-dontwarn com.yausername.**
-dontwarn org.apache.commons.compress.**
-keep class org.tukaani.xz.** { *; }
-dontwarn org.tukaani.xz.**

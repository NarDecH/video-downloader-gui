# NewPipeExtractor uses nanojson + jsoup; keep them from being stripped
-keep class org.nanojson.** { *; }
-keep class org.jsoup.** { *; }
-keep class org.schabi.newpipe.extractor.** { *; }
-dontwarn org.mozilla.javascript.**
-dontwarn org.mozilla.classfile.**

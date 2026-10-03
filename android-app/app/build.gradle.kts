plugins {
    id("com.android.application")
}

android {
    namespace = "com.ayano.tesahostify"
    //noinspection GradleDependency
    compileSdk = 36
    buildToolsVersion = "36.0.0"

    defaultConfig {
        applicationId = "com.ayano.tesahostify"
        minSdk = 26
        //noinspection EditedTargetSdkVersion,OldTargetApi
        targetSdk = 36
        versionCode = 1
        versionName = "1.0"
    }
}

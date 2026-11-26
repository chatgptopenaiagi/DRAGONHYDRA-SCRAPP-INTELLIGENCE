# Distribution engineering

The published v0.3.0-beta.1 tag identifies the original Windows/source commit 0594876a2ebd6944b7a44ae54f7603d3790e93cd. The additive Android and Python source is identified separately in the release's DISTRIBUTION-007 association. Keep the original assets and verification records. Publish additive aggregate evidence with distinct filenames.

## Python

The distribution wraps the existing application packages and living_launch bootstrap through setuptools. The public facade delegates to the workstation calculation, statistical, storage, normalization and provider modules. The wheel includes both sets of dashboard resources, the archived aggregate backtest and SQL schema. Its workstation extra is optional.

Use a new Python 3.13 environment. The verified build used build 1.6.1, setuptools 84.2.1, wheel 0.48.0 and SOURCE_DATE_EPOCH 1795684583.

    python -m pip install build==1.6.1 setuptools==84.2.1 wheel==0.48.0
    $env:SOURCE_DATE_EPOCH = '1795684583'
    python -m build --wheel --no-isolation --outdir ../packages

Install the wheel in a fresh environment. Copy tools/verify_installed_wheel.py to a directory outside the checkout and run it there with the environment's python -I. For the original regression suite, install requirements.txt in that test environment and copy tests and tools/backtest_seasons.py into matching directories under the external test root. Run python -I -m unittest discover -s tests -v there. The external root should contain no application source directory. The standalone smoke test also runs in an environment containing only the wheel.

## Android

The Java Activity hosts locally bundled HTML, CSS and JavaScript. Its WebView resolves an allowlist of three application resources. The bridge exposes deterministic calculations, archived model scores, SQLite history, theme preferences and the Android document picker. The manifest has no network or storage permission. A bounded transactional import validates every observation before commit. The acceptance instrumentation is built separately and is excluded from the release APK.

Set ANDROID_HOME to an SDK containing platform android-36 and build-tools 36.0.0. Set JAVA_HOME to a JDK with javac, jar and keytool. The verified build used Android Studio's bundled JDK. SDK tools aapt2, d8, zipalign and apksigner perform resource linking, dex compilation, alignment and signing. Gradle, Kotlin, Flutter and the NDK are unnecessary for this implementation.

Provide a PKCS12 release keystore with alias dragonhydra and set DH_SIGN_PASSWORD through the local secret manager. Keep this key for updates. The distribution workstation protects its password with Windows user-bound DPAPI. Archive the key and recoverable credentials in the owner's secure backup before moving to another workstation. Repository and release assets contain only the public certificate embedded in the APK.

    python android/build.py --keystore PRIVATE_KEYSTORE --out ../packages/DRAGONHYDRA-Intelligence-0.3.0-beta.1-android-universal.apk
    python android/build.py --instrumentation --keystore PRIVATE_KEYSTORE --out ../android-acceptance.apk
    python android/verify.py --serial emulator-5582 --apk ../packages/DRAGONHYDRA-Intelligence-0.3.0-beta.1-android-universal.apk --test-apk ../android-acceptance.apk --out ../acceptance

Use a disposable English-language Android emulator with DocumentsUI for the acceptance command. It selects airplane mode, performs clean installation, imports a labelled synthetic document through the system picker, verifies exports, exercises rotation, Android Back, restart and same-version reinstall, and uninstalls both packages. It records timings, installed bytes, memory and idle CPU. For numerical equivalence, run tools/verify_distribution_math.py from the installed wheel environment with --python, --source-launcher, --portable, --android (the acceptance report) and --out. Each original server runs in a fresh offline directory. The shared numerical tolerance is 1e-30 × max(abs(reference), 1e-25).

## Recovery

The unchanged tag and original verification files identify the original Windows distributions. Android JSON export restores local observation history after a clean install. Android application updates require the same package ID and signing identity. Python removal uses python -m pip uninstall dragonhydra-intelligence after stopping the dashboard. The selected SQLite profile remains available for later use.

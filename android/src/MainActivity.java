package io.github.chatgptopenaiagi.dragonhydra;

import android.app.Activity;
import android.os.Bundle;
import android.content.Intent;
import android.net.Uri;
import android.view.View;
import android.webkit.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import org.json.*;

public final class MainActivity extends Activity {
    WebView web;
    Ledger ledger;
    private final ExecutorService documents = Executors.newSingleThreadExecutor();
    private static final int OPEN = 10, JSON = 11, CSV = 12;
    private static final String ORIGIN = "https://dragonhydra.invalid/";
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        ledger = new Ledger(this);
        web = new WebView(this);
        setContentView(web);
        findViewById(android.R.id.content).setOnApplyWindowInsetsListener((v,insets)->{
            v.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),
                         insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom());
            return insets.consumeSystemWindowInsets();
        });
        WebSettings settings = web.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setBlockNetworkLoads(true);
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView v,WebResourceRequest req) { return true; }
            @Override public WebResourceResponse shouldInterceptRequest(WebView v, WebResourceRequest req) {
                String url=req.getUrl().toString();
                if(url.startsWith(ORIGIN)) {
                    String file=url.substring(ORIGIN.length());
                    String mime=file.equals("index.html")?"text/html":file.equals("app.js")?"text/javascript":file.equals("style.css")?"text/css":null;
                    if(mime!=null) try {
                        return new WebResourceResponse(mime,"UTF-8",200,"OK",Collections.singletonMap("X-Content-Type-Options","nosniff"),getAssets().open(file));
                    } catch(IOException ignored) {}
                }
                return new WebResourceResponse("text/plain","UTF-8",404,"Missing",Collections.emptyMap(),null);
            }
        });
        web.addJavascriptInterface(new Bridge(),"Local");
        web.loadUrl(ORIGIN+"index.html");
    }

    private static String read(InputStream stream) throws IOException {
        try(InputStream input=stream; ByteArrayOutputStream out=new ByteArrayOutputStream()) {
            byte[] chunk=new byte[8192]; int n;
            while((n=input.read(chunk))!=-1) {
                if(out.size()+n>4*1024*1024) throw new IOException("Document exceeds 4 MiB");
                out.write(chunk,0,n);
            }
            return out.toString("UTF-8");
        }
    }

    interface Operation { Object run() throws Exception; }
    static String response(Operation op) {
        JSONObject envelope=new JSONObject();
        try { envelope.put("data",op.run()); }
        catch(Exception error) { try { envelope.put("error",error.getMessage()==null?"Invalid input":error.getMessage()); } catch(JSONException ignored) {} }
        return envelope.toString();
    }
    final class Bridge {
        @JavascriptInterface public String calculate(String body) { return response(()->Market.calculate(new JSONObject(body))); }
        @JavascriptInterface public String history() { return response(()->ledger.all()); }
        @JavascriptInterface public String evidence() { return response(()->new JSONObject(read(getAssets().open("backtest.json")))); }
        @JavascriptInterface public String theme() { return getPreferences(0).getString("theme","system"); }
        @JavascriptInterface public void saveTheme(String name) {
            if(name.equals("system")||name.equals("dark")||name.equals("light")) getPreferences(0).edit().putString("theme",name).apply();
        }
        @JavascriptInterface public void selectDocument(String action) {
            runOnUiThread(()->{
                int code=action.equals("import")?OPEN:action.equals("csv")?CSV:JSON;
                Intent intent=new Intent(code==OPEN?Intent.ACTION_OPEN_DOCUMENT:Intent.ACTION_CREATE_DOCUMENT)
                    .addCategory(Intent.CATEGORY_OPENABLE).setType(code==CSV?"text/csv":"application/json");
                if(code!=OPEN) intent.putExtra(Intent.EXTRA_TITLE,code==CSV?"dragonhydra-history.csv":"dragonhydra-history.json");
                try { startActivityForResult(intent,code); }
                catch(android.content.ActivityNotFoundException e) { notifyPage("Document picker unavailable"); }
            });
        }
    }
    private void notifyPage(String message) {
        runOnUiThread(()->{if(!isDestroyed()) web.evaluateJavascript("window.documentResult("+JSONObject.quote(message)+")",null);});
    }
    @Override protected void onActivityResult(int code,int result,Intent data) {
        super.onActivityResult(code,result,data);
        if(result!=RESULT_OK || data==null || data.getData()==null) return;
        Uri uri=data.getData();
        if(!"content".equals(uri.getScheme())) {notifyPage("Choose a document from the system picker");return;}
        documents.execute(()->{
            try {
                if(code==OPEN) {
                    int n=ledger.ingest(new JSONObject(read(getContentResolver().openInputStream(uri))));
                    notifyPage(n+" observations imported");
                } else if(code==JSON||code==CSV) {
                    String text=code==JSON?ledger.all().toString(2):ledger.csv();
                    try(OutputStream out=getContentResolver().openOutputStream(uri,"wt")) {out.write(text.getBytes(StandardCharsets.UTF_8));}
                    notifyPage("Export saved");
                }
            } catch(Exception e) {notifyPage("Document error: "+e.getMessage());}
        });
    }
    @Override public void onBackPressed() {
        web.evaluateJavascript("typeof backTab === 'function' && backTab()",v->{if(!"true".equals(v)) finish();});
    }
    @Override protected void onDestroy() {
        documents.execute(()->ledger.close()); documents.shutdown();
        web.removeJavascriptInterface("Local"); web.destroy(); super.onDestroy();
    }
}

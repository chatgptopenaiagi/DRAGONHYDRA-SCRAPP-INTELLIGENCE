package io.github.chatgptopenaiagi.dragonhydra.acceptance;

import android.app.*;
import android.content.*;
import android.content.pm.ActivityInfo;
import android.os.*;
import android.view.*;
import android.view.accessibility.*;
import android.webkit.WebView;
import android.widget.FrameLayout;
import java.io.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;
import org.json.*;

public final class Acceptance extends Instrumentation {
    private Activity activity;
    private WebView web;
    private Bundle args;
    private final JSONArray passed=new JSONArray();
    @Override public void onCreate(Bundle args){this.args=args;start();}
    private String js(String expression) throws Exception {
        AtomicReference<String> result=new AtomicReference<>();
        CountDownLatch done=new CountDownLatch(1);
        runOnMainSync(()->web.evaluateJavascript(expression,value->{result.set(value);done.countDown();}));
        if(!done.await(15,TimeUnit.SECONDS))throw new AssertionError("WebView timeout");
        return result.get();
    }
    private void waitFor(String expr) throws Exception {
        for(int i=0;i<100;i++){if("true".equals(js(expr)))return;SystemClock.sleep(100);}
        throw new AssertionError("Timed out: "+expr+"; page="+js("document.body.innerText.slice(0,500)"));
    }
    private void test(String name,boolean ok){if(!ok)throw new AssertionError(name);passed.put(name);}
    private void touch(String selector) throws Exception {
        JSONArray pt=new JSONArray(js("(()=>{const b=document.querySelector("+JSONObject.quote(selector)+").getBoundingClientRect();return [(b.left+b.width/2)*devicePixelRatio,(b.top+b.height/2)*devicePixelRatio]})()"));
        int[] pos=new int[2];runOnMainSync(()->web.getLocationOnScreen(pos));
        float x=pos[0]+(float)pt.getDouble(0),y=pos[1]+(float)pt.getDouble(1);
        long when=SystemClock.uptimeMillis();
        for(int action:new int[]{MotionEvent.ACTION_DOWN,MotionEvent.ACTION_UP}){
            MotionEvent e=MotionEvent.obtain(when,SystemClock.uptimeMillis(),action,x,y,0);e.setSource(InputDevice.SOURCE_TOUCHSCREEN);
            getUiAutomation().injectInputEvent(e,true);e.recycle();
        }
    }
    private AccessibilityNodeInfo find(AccessibilityNodeInfo n,String label) {
        if(n==null)return null;
        if(label.equalsIgnoreCase(String.valueOf(n.getText()))||label.equalsIgnoreCase(String.valueOf(n.getContentDescription())))return n;
        for(int i=0;i<n.getChildCount();i++){AccessibilityNodeInfo hit=find(n.getChild(i),label);if(hit!=null)return hit;}
        return null;
    }
    private boolean clickSystem(String label,int attempts){
        for(int i=0;i<attempts;i++){
            AccessibilityNodeInfo n=find(getUiAutomation().getRootInActiveWindow(),label);
            while(n!=null){if(n.isClickable()&&n.performAction(AccessibilityNodeInfo.ACTION_CLICK))return true;n=n.getParent();}
            SystemClock.sleep(200);
        }return false;
    }
    private void requireSystem(String label){if(!clickSystem(label,40))throw new AssertionError("Picker control missing: "+label);}
    private void downloadFolder(){
        if(clickSystem("Show roots",10)||clickSystem("Open navigation drawer",3))requireSystem("Downloads");
    }
    private void doc(String action,String message) throws Exception {
        js("document.getElementById("+JSONObject.quote(action)+").click()");SystemClock.sleep(800);
        if(action.equals("import")){
            if(!clickSystem("dragonhydra-qa-fixture.json",3)){downloadFolder();requireSystem("dragonhydra-qa-fixture.json");}
        } else { downloadFolder();requireSystem("Save");clickSystem("Replace",3); }
        waitFor("document.getElementById('docstatus').textContent==="+JSONObject.quote(message));
    }
    private JSONArray vectors() throws Exception {
        try(BufferedReader r=new BufferedReader(new InputStreamReader(getContext().getAssets().open("scenarios.json"),"UTF-8"))){
            StringBuilder s=new StringBuilder();String line;while((line=r.readLine())!=null)s.append(line);
            return new JSONArray(s.toString());
        }
    }
    @Override public void onStart(){
        Bundle status=new Bundle();JSONObject report=new JSONObject();
        try {
            Intent intent=getTargetContext().getPackageManager().getLaunchIntentForPackage(getTargetContext().getPackageName());
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_CLEAR_TASK);
            activity=startActivitySync(intent);
            runOnMainSync(()->web=(WebView)((FrameLayout)activity.findViewById(android.R.id.content)).getChildAt(0));
            waitFor("typeof current!=='undefined' && document.getElementById('games').textContent.replace(/[^0-9]/g,'')==='2744'");
            test("offline dashboard and archived evidence",true);
            if("persist".equals(args.getString("stage"))){
                waitFor("historyRows.length===3 && Local.theme()==='dark'");
                test("SQLite and theme survived process restart or reinstall",true);
            } else {
                touch("button[data-page=calculator]");waitFor("current==='calculator'");test("touch navigation",true);
                js("document.getElementById('calculate').click()");waitFor("document.getElementById('result').innerText.includes('Normalized')");
                test("rendered calculator results",true);
                JSONObject observed=new JSONObject();
                JSONArray vectors=vectors();
                for(int i=0;i<vectors.length();i++){
                    JSONObject sample=vectors.getJSONObject(i);
                    JSONObject reply=new JSONObject(js("JSON.parse(Local.calculate("+JSONObject.quote(sample.getJSONObject("body").toString())+"))"));
                    if(reply.has("data")!=sample.getBoolean("valid"))throw new AssertionError(sample.getString("id")+reply);
                    observed.put(sample.getString("id"),reply.has("data")?reply.get("data"):new JSONObject().put("invalid",true));
                }
                report.put("vectors",observed);test("15 shared market vectors executed",true);
                js("document.getElementById('price-first').value='0';document.getElementById('calculate').click()");
                waitFor("document.getElementById('result').innerText.includes('Check your inputs')");test("invalid input feedback",true);
                runOnMainSync(()->activity.setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE));
                waitFor("innerWidth>innerHeight && current==='calculator' && document.getElementById('price-first').value==='0'");
                runOnMainSync(()->activity.setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_PORTRAIT));
                waitFor("innerHeight>innerWidth");test("rotation retained edited inputs",true);
                sendKeyDownUpSync(KeyEvent.KEYCODE_BACK);waitFor("current==='overview'");test("Android Back restored overview",true);
                js("el('theme').value='dark';el('theme').dispatchEvent(new Event('change'))");
                waitFor("Local.theme()==='dark' && document.documentElement.dataset.theme==='dark'");test("persistent appearance",true);
                touch("button[data-page=history]");waitFor("current==='history'");
                doc("import","3 observations imported");doc("import","0 observations imported");
                test("system document import and SQLite duplicate prevention",true);
                waitFor("document.querySelectorAll('#movement circle').length===3");
                js("el('query').value='absent';el('query').dispatchEvent(new Event('input'))");
                waitFor("el('records').innerText.includes('No matching')");
                js("el('query').value='';el('query').dispatchEvent(new Event('input'))");
                test("historical chart and filtering",true);
                doc("json","Export saved");js("el('docstatus').textContent=''");
                doc("csv","Export saved");test("JSON and CSV system document exports",true);
            }
            android.content.Context target=getTargetContext();
            android.app.usage.StorageStatsManager sm=target.getSystemService(android.app.usage.StorageStatsManager.class);
            android.app.usage.StorageStats size=sm.queryStatsForUid(android.os.storage.StorageManager.UUID_DEFAULT,target.getApplicationInfo().uid);
            report.put("storage",new JSONObject().put("app_bytes",size.getAppBytes()).put("data_bytes",size.getDataBytes()).put("cache_bytes",size.getCacheBytes()));
            report.put("viewport",new JSONArray(js("[innerWidth,innerHeight]")));
            report.put("checks",passed);status.putString("report",report.toString());finish(Activity.RESULT_OK,status);
        } catch(Throwable e){status.putString("failure",android.util.Log.getStackTraceString(e));status.putString("passed",passed.toString());finish(Activity.RESULT_CANCELED,status);}
    }
}

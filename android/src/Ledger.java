package io.github.chatgptopenaiagi.dragonhydra;

import android.content.Context;
import android.database.Cursor;
import android.database.sqlite.*;
import java.time.OffsetDateTime;
import org.json.*;

final class Ledger extends SQLiteOpenHelper {
    static final String SCHEMA = "dh.mobile-history/1";
    static final String[] FIELDS = {"event","source","selection","at","decimal"};
    static final int CAP = 2000;
    Ledger(Context context) { super(context,"history.sqlite",null,1); }
    public void onCreate(SQLiteDatabase db) {
        db.execSQL("CREATE TABLE quotes(event TEXT,source TEXT,selection TEXT,at TEXT,decimal TEXT, PRIMARY KEY(event,source,selection,at,decimal))");
    }
    public void onUpgrade(SQLiteDatabase db,int old,int next) { throw new IllegalStateException("Unsupported database version"); }

    synchronized JSONObject all() throws JSONException {
        JSONArray rows = new JSONArray();
        try (Cursor c = getReadableDatabase().rawQuery("SELECT event,source,selection,at,decimal FROM quotes ORDER BY at,event,source,selection,decimal",null)) {
            while (c.moveToNext()) {
                JSONObject row = new JSONObject();
                for (int i=0;i<FIELDS.length;i++) row.put(FIELDS[i],c.getString(i));
                rows.put(row);
            }
        }
        return new JSONObject().put("schema",SCHEMA).put("market","full-time match winner").put("observations",rows);
    }

    synchronized int ingest(JSONObject doc) throws JSONException {
        Market.check(SCHEMA.equals(doc.getString("schema")) && "full-time match winner".equals(doc.getString("market")), "Expected a DRAGONHYDRA full-time match winner history document");
        JSONArray rows = doc.getJSONArray("observations");
        Market.check(rows.length() <= CAP,"Import exceeds 2,000 observations");
        SQLiteDatabase db = getWritableDatabase();
        db.beginTransaction();
        try (SQLiteStatement add = db.compileStatement("INSERT OR IGNORE INTO quotes VALUES(?,?,?,?,?)")) {
            int added = 0;
            for (int i=0;i<rows.length();i++) {
                JSONObject row = rows.getJSONObject(i);
                Market.check(row.length()==FIELDS.length,"Unexpected observation fields");
                for (int j=0;j<FIELDS.length;j++) {
                    Object value = row.get(FIELDS[j]);
                    Market.check(value instanceof String,"Observation fields must be text");
                    String s = ((String)value).trim();
                    Market.check(!s.isEmpty() && s.length()<=200 && !s.matches("(?s).*\\p{Cntrl}.*"),"Missing or invalid observation field");
                    if (j==3) s = new java.time.format.DateTimeFormatterBuilder().appendInstant(9).toFormatter().format(OffsetDateTime.parse(s).toInstant());
                    if (j==4) s = Market.price(s,"decimal").stripTrailingZeros().toPlainString();
                    add.bindString(j+1,s);
                }
                if(add.executeInsert()!=-1) added++;
            }
            try(Cursor c=db.rawQuery("SELECT count(*) FROM quotes",null)) {
                c.moveToFirst(); Market.check(c.getInt(0)<=CAP,"Local history capacity is 2,000 observations");
            }
            db.setTransactionSuccessful();
            return added;
        } finally { db.endTransaction(); }
    }

    synchronized String csv() throws JSONException {
        StringBuilder out = new StringBuilder("market,event,source,selection,at,decimal\r\n");
        JSONArray rows = all().getJSONArray("observations");
        for(int i=0;i<rows.length();i++) {
            JSONObject row = rows.getJSONObject(i);
            out.append("full-time match winner");
            for(String field : FIELDS) {
                String s=row.getString(field);
                if("=+-@".indexOf(s.charAt(0))>=0) s="'"+s;
                out.append(",\"").append(s.replace("\"","\"\"")).append("\"");
            }
            out.append("\r\n");
        }
        return out.toString();
    }
}

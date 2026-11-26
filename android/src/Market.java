package io.github.chatgptopenaiagi.dragonhydra;

import java.math.BigDecimal;
import java.math.MathContext;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.json.*;

final class Market {
    private static final MathContext MC = MathContext.DECIMAL128;
    private static final BigDecimal ONE = BigDecimal.ONE, HUNDRED = BigDecimal.valueOf(100);
    private static final Pattern FRACTION = Pattern.compile("\\s*(\\d+)\\s*/\\s*(\\d+)\\s*");

    static void check(boolean valid, String message) {
        if (!valid) throw new IllegalArgumentException(message);
    }

    private static int adjusted(BigDecimal n) { return n.precision() - n.scale() - 1; }

    static BigDecimal price(String raw, String format) {
        check(raw.length() <= 80, "Price exceeds 80 characters");
        BigDecimal d;
        if ("fractional".equals(format)) {
            Matcher m = FRACTION.matcher(raw);
            check(m.matches(), "Use a positive fraction such as 5/2");
            BigDecimal a = new BigDecimal(m.group(1)), b = new BigDecimal(m.group(2));
            check(a.signum() > 0 && b.signum() > 0, "Both fraction terms must be positive");
            d = ONE.add(a.divide(b, MC), MC);
        } else {
            BigDecimal n = new BigDecimal(raw.trim());
            check(Math.abs((long)adjusted(n)) <= 25, "Price exceeds the supported range");
            if ("decimal".equals(format)) d = n;
            else {
                check("american".equals(format), "Unknown format");
                check(n.stripTrailingZeros().scale() <= 0 && n.abs().compareTo(HUNDRED) >= 0, "American prices must be whole numbers of magnitude at least 100");
                d = ONE.add(n.signum() > 0 ? n.divide(HUNDRED, MC) : HUNDRED.divide(n.negate(), MC), MC);
            }
        }
        d = d.round(MC);
        check(d.compareTo(ONE) > 0, "Decimal odds must exceed one at the supported precision");
        return d;
    }

    static JSONObject calculate(JSONObject body) throws JSONException {
        String type = body.getString("market");
        check(type.equals("1X2") || type.equals("two-way"), "Unknown market");
        String[] names = type.equals("1X2") ? new String[]{"home","draw","away"} : new String[]{"first","second"};
        java.util.Iterator<String> keys = body.keys();
        while (keys.hasNext()) check(java.util.Arrays.asList("market","format","prices","assumption").contains(keys.next()), "Unexpected input");
        String format = body.optString("format","decimal");
        JSONObject prices = body.getJSONObject("prices"), rows = new JSONObject();
        check(prices.length() == names.length, "Supply one price per outcome");
        BigDecimal total = BigDecimal.ZERO;
        for (String name : names) {
            BigDecimal d = price(prices.getString(name), format), q = ONE.divide(d, MC);
            rows.put(name, new JSONObject().put("decimal",d.toString()).put("implied",q.toString()));
            total = total.add(q, MC);
        }
        for (String name : names) {
            JSONObject row = rows.getJSONObject(name);
            BigDecimal p = new BigDecimal(row.getString("implied")).divide(total, MC);
            row.put("normalized",p.toString()).put("fair_decimal",ONE.divide(p, MC).toString());
        }
        Object ev = JSONObject.NULL;
        if (!body.isNull("assumption")) {
            JSONObject a = body.getJSONObject("assumption");
            String name = a.getString("outcome"), raw = a.getString("probability");
            check(a.get("basis") instanceof String, "Explain the probability assumption");
            String basis = a.getString("basis").trim();
            check(a.length() == 3 && rows.has(name) && !basis.isEmpty() && basis.length() <= 200 && raw.length() <= 80,"Invalid EV assumption");
            BigDecimal p = new BigDecimal(raw.trim());
            check(p.signum() >= 0 && p.compareTo(ONE) <= 0 && (p.signum()==0 || adjusted(p)>=-100), "Assumed probability must be between 0 and 1");
            BigDecimal d = new BigDecimal(rows.getJSONObject(name).getString("decimal"));
            ev = new JSONObject().put("outcome",name).put("probability",p.toString()).put("basis",basis)
                .put("net_per_unit",p.multiply(d,MC).subtract(ONE,MC).toString());
        }
        return new JSONObject().put("schema","dh.market/1").put("category","MATHEMATICAL CALCULATION").put("input",body)
            .put("book_total",total.toString()).put("overround",total.subtract(ONE,MC).toString())
            .put("theoretical_margin",ONE.subtract(ONE.divide(total,MC),MC).toString()).put("outcomes",rows).put("expected_value",ev);
    }
}

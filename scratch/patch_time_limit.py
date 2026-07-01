import os

target_file = "/Users/Zhuanz/Downloads/DeepSeek_EA_v4.50.mq5"

with open(target_file, "rb") as f:
    content = f.read().decode('utf-8', errors='ignore')

content_norm = content.replace('\r\n', '\n')

# 1. Add allowed time window inputs
inputs_target = "input double            InpDailyDDPct    = 10.0;   // 每日最大回撤百分比(%)，触发后当天停止"
inputs_replacement = """input double            InpDailyDDPct    = 10.0;   // 每日最大回撤百分比(%)，触发后当天停止
input int               InpStartHour     = 0;      // 允许交易起始小时 (0-23)
input int               InpStartMinute   = 0;      // 允许交易起始分钟 (0-59)
input int               InpEndHour       = 14;     // 允许交易结束小时 (0-23)
input int               InpEndMinute     = 0;      // 允许交易结束分钟 (0-59)"""

if inputs_target in content_norm:
    content_norm = content_norm.replace(inputs_target, inputs_replacement)
    print("1. Inputs successfully patched!")
else:
    print("ERROR: Inputs target not found!")

# 2. Add IsTimeAllowed helper function before Global Variables section
glob_target = "//--- Global Variables"
helper_func = """//+------------------------------------------------------------------+
//| Check if the current server time is in the allowed window        |
//+------------------------------------------------------------------+
bool IsTimeAllowed()
  {
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   
   int current_minutes = dt.hour * 60 + dt.min;
   int start_minutes = InpStartHour * 60 + InpStartMinute;
   int end_minutes = InpEndHour * 60 + InpEndMinute;
   
   if(start_minutes <= end_minutes)
     {
      return (current_minutes >= start_minutes && current_minutes <= end_minutes);
     }
   else
     {
      // Handle crossing midnight
      return (current_minutes >= start_minutes || current_minutes <= end_minutes);
     }
  }

//--- Global Variables"""

if glob_target in content_norm:
    content_norm = content_norm.replace(glob_target, helper_func)
    print("2. IsTimeAllowed helper successfully inserted!")
else:
    print("ERROR: Global Variables header not found!")

# 3. Modify OnTick() auto-monitor logic to skip analysis outside allowed hours
ontick_target = """    if(is_auto_monitor && !is_thinking && !g_daily_dd_triggered) {
       long cd_left = 300 - (long)(TimeCurrent() - last_ai_call_time);
       if(cd_left > 0) {
          string cd_str = "⏳ 冷却中: " + IntegerToString((int)(cd_left/60)) + "m" + IntegerToString((int)(cd_left%60)) + "s";
          ObjectSetString(0, panel_name + "_cd_label", OBJPROP_TEXT, cd_str);
          ObjectSetInteger(0, panel_name + "_cd_label", OBJPROP_COLOR, clrGray);
       } else {
          double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
          double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
          double mid = (ask + bid) / 2.0;
          
          // ④ 多条件触发：布林带边界 OR RSI超买超卖 OR 价格突破EMA±ATR
          bool bb_trigger  = (g_bb_up > 0 && ask >= g_bb_up) || (g_bb_dn > 0 && bid <= g_bb_dn);
          bool rsi_trigger = (g_rsi > 0) && (g_rsi >= 70.0 || g_rsi <= 30.0);
          bool ema_trigger = (g_ema > 0 && g_atr > 0) &&
                             (mid >= g_ema + g_atr || mid <= g_ema - g_atr);
          
          string trigger_reason = "";
          if(bb_trigger)  trigger_reason = "布林带边界";
          if(rsi_trigger) trigger_reason = (StringLen(trigger_reason)>0 ? trigger_reason+"+" : "") + "RSI超"+(g_rsi>=70?"买":"卖");
          if(ema_trigger) trigger_reason = (StringLen(trigger_reason)>0 ? trigger_reason+"+" : "") + "价格偏离EMA";
          
          if(bb_trigger || rsi_trigger || ema_trigger) {
             if(InpDebugMode) Print("[AUTO] 🚨 触发: ", trigger_reason, " | Ask:", ask, " RSI:", g_rsi, " EMA:", g_ema);
             last_ai_call_time = TimeCurrent();
             
             ObjectSetString(0, panel_name + "_cd_label", OBJPROP_TEXT, "🤖 分析中...");
             ObjectSetInteger(0, panel_name + "_cd_label", OBJPROP_COLOR, clrOrange);
             is_thinking = true;
             ObjectSetString(0, panel_name + "_ai_txt1", OBJPROP_TEXT, "[" + trigger_reason + "] 触发自动监控，深度分析中...");
             ObjectSetString(0, panel_name + "_ai_keys", OBJPROP_TEXT, " ");
             for(int i=0; i<7; i++) ObjectSetString(0, panel_name + "_ai_r" + IntegerToString(i), OBJPROP_TEXT, " ");
             ObjectSetInteger(0, panel_name + "_ai_txt1", OBJPROP_COLOR, clrOrange);
             ChartRedraw();
             
             ExecuteDeepSeekAnalysis();
             
             is_thinking = false;
             ObjectSetString(0, panel_name + "_ai_txt1", OBJPROP_TEXT, last_ai_result_1);
             ObjectSetString(0, panel_name + "_ai_keys", OBJPROP_TEXT, last_ai_result_keys);
             for(int i=0; i<7; i++) ObjectSetString(0, panel_name + "_ai_r" + IntegerToString(i), OBJPROP_TEXT, last_ai_reason[i]);
             ObjectSetInteger(0, panel_name + "_ai_txt1", OBJPROP_COLOR, clrWhite);
             ObjectSetString(0, panel_name + "_cd_label", OBJPROP_TEXT, "✅ 分析完成");
             ObjectSetInteger(0, panel_name + "_cd_label", OBJPROP_COLOR, clrLimeGreen);
             ChartRedraw();
          } else {
             ObjectSetString(0, panel_name + "_cd_label", OBJPROP_TEXT, "🟢 就绪 | 等待信号");
             ObjectSetInteger(0, panel_name + "_cd_label", OBJPROP_COLOR, clrLimeGreen);
          }
       }
    }"""

ontick_replacement = """    if(is_auto_monitor && !is_thinking && !g_daily_dd_triggered) {
       if(!IsTimeAllowed()) {
          string time_str = StringFormat("💤 非交易时段 (%02d:%02d-%02d:%02d)", InpStartHour, InpStartMinute, InpEndHour, InpEndMinute);
          ObjectSetString(0, panel_name + "_cd_label", OBJPROP_TEXT, time_str);
          ObjectSetInteger(0, panel_name + "_cd_label", OBJPROP_COLOR, clrOrange);
          ChartRedraw();
       } else {
          long cd_left = 300 - (long)(TimeCurrent() - last_ai_call_time);
          if(cd_left > 0) {
             string cd_str = "⏳ 冷却中: " + IntegerToString((int)(cd_left/60)) + "m" + IntegerToString((int)(cd_left%60)) + "s";
             ObjectSetString(0, panel_name + "_cd_label", OBJPROP_TEXT, cd_str);
             ObjectSetInteger(0, panel_name + "_cd_label", OBJPROP_COLOR, clrGray);
          } else {
             double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
             double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
             double mid = (ask + bid) / 2.0;
             
             // ④ 多条件触发：布林带边界 OR RSI超买超卖 OR 价格突破EMA±ATR
             bool bb_trigger  = (g_bb_up > 0 && ask >= g_bb_up) || (g_bb_dn > 0 && bid <= g_bb_dn);
             bool rsi_trigger = (g_rsi > 0) && (g_rsi >= 70.0 || g_rsi <= 30.0);
             bool ema_trigger = (g_ema > 0 && g_atr > 0) &&
                                (mid >= g_ema + g_atr || mid <= g_ema - g_atr);
             
             string trigger_reason = "";
             if(bb_trigger)  trigger_reason = "布林带边界";
             if(rsi_trigger) trigger_reason = (StringLen(trigger_reason)>0 ? trigger_reason+"+" : "") + "RSI超"+(g_rsi>=70?"买":"卖");
             if(ema_trigger) trigger_reason = (StringLen(trigger_reason)>0 ? trigger_reason+"+" : "") + "价格偏离EMA";
             
             if(bb_trigger || rsi_trigger || ema_trigger) {
                if(InpDebugMode) Print("[AUTO] 🚨 触发: ", trigger_reason, " | Ask:", ask, " RSI:", g_rsi, " EMA:", g_ema);
                last_ai_call_time = TimeCurrent();
                
                ObjectSetString(0, panel_name + "_cd_label", OBJPROP_TEXT, "🤖 分析中...");
                ObjectSetInteger(0, panel_name + "_cd_label", OBJPROP_COLOR, clrOrange);
                is_thinking = true;
                ObjectSetString(0, panel_name + "_ai_txt1", OBJPROP_TEXT, "[" + trigger_reason + "] 触发自动监控，深度分析中...");
                ObjectSetString(0, panel_name + "_ai_keys", OBJPROP_TEXT, " ");
                for(int i=0; i<7; i++) ObjectSetString(0, panel_name + "_ai_r" + IntegerToString(i), OBJPROP_TEXT, " ");
                ObjectSetInteger(0, panel_name + "_ai_txt1", OBJPROP_COLOR, clrOrange);
                ChartRedraw();
                
                ExecuteDeepSeekAnalysis();
                
                is_thinking = false;
                ObjectSetString(0, panel_name + "_ai_txt1", OBJPROP_TEXT, last_ai_result_1);
                ObjectSetString(0, panel_name + "_ai_keys", OBJPROP_TEXT, last_ai_result_keys);
                for(int i=0; i<7; i++) ObjectSetString(0, panel_name + "_ai_r" + IntegerToString(i), OBJPROP_TEXT, last_ai_reason[i]);
                ObjectSetInteger(0, panel_name + "_ai_txt1", OBJPROP_COLOR, clrWhite);
                ObjectSetString(0, panel_name + "_cd_label", OBJPROP_TEXT, "✅ 分析完成");
                ObjectSetInteger(0, panel_name + "_cd_label", OBJPROP_COLOR, clrLimeGreen);
                ChartRedraw();
             } else {
                ObjectSetString(0, panel_name + "_cd_label", OBJPROP_TEXT, "🟢 就绪 | 等待信号");
                ObjectSetInteger(0, panel_name + "_cd_label", OBJPROP_COLOR, clrLimeGreen);
             }
          }
       }
    }"""

if ontick_target in content_norm:
    content_norm = content_norm.replace(ontick_target, ontick_replacement)
    print("3. OnTick auto-monitor successfully patched!")
else:
    print("ERROR: OnTick target not found!")

# 4. Modify OnTimer() CD timer refresh logic to handle allowed hours
ontimer_target = """    if(is_auto_monitor && !is_thinking && !g_daily_dd_triggered)
      {
       long cd_left = 300 - (long)(TimeCurrent() - last_ai_call_time);
       if(cd_left > 0)
         {
          string cd_str = "⏳ 冷却中: " + IntegerToString((int)(cd_left/60)) + "m" + IntegerToString((int)(cd_left%60)) + "s";
          ObjectSetString(0, panel_name + "_cd_label", OBJPROP_TEXT, cd_str);
         }
      }"""

ontimer_replacement = """    if(is_auto_monitor && !is_thinking && !g_daily_dd_triggered)
      {
       if(!IsTimeAllowed())
         {
          string time_str = StringFormat("💤 非交易时段 (%02d:%02d-%02d:%02d)", InpStartHour, InpStartMinute, InpEndHour, InpEndMinute);
          ObjectSetString(0, panel_name + "_cd_label", OBJPROP_TEXT, time_str);
          ObjectSetInteger(0, panel_name + "_cd_label", OBJPROP_COLOR, clrOrange);
         }
       else
         {
          long cd_left = 300 - (long)(TimeCurrent() - last_ai_call_time);
          if(cd_left > 0)
            {
             string cd_str = "⏳ 冷却中: " + IntegerToString((int)(cd_left/60)) + "m" + IntegerToString((int)(cd_left%60)) + "s";
             ObjectSetString(0, panel_name + "_cd_label", OBJPROP_TEXT, cd_str);
             ObjectSetInteger(0, panel_name + "_cd_label", OBJPROP_COLOR, clrGray);
            }
          else
            {
             ObjectSetString(0, panel_name + "_cd_label", OBJPROP_TEXT, "🟢 就绪 | 等待信号");
             ObjectSetInteger(0, panel_name + "_cd_label", OBJPROP_COLOR, clrLimeGreen);
            }
         }
      }"""

if ontimer_target in content_norm:
    content_norm = content_norm.replace(ontimer_target, ontimer_replacement)
    print("4. OnTimer successfully patched!")
else:
    print("ERROR: OnTimer target not found!")

# 5. Modify OnChartEvent Ask Button click handler
onchart_target = """       else if(sparam == panel_name + "_btn_ask")
         {
          if(is_thinking) return;
          is_thinking = true;
          ObjectSetString(0, panel_name + "_ai_txt1", OBJPROP_TEXT, "正在深度运算与思考中，请稍候...");
          ObjectSetString(0, panel_name + "_ai_keys", OBJPROP_TEXT, " ");
          for(int i=0; i<7; i++) ObjectSetString(0, panel_name + "_ai_r" + IntegerToString(i), OBJPROP_TEXT, " ");
          ObjectSetInteger(0, panel_name + "_ai_txt1", OBJPROP_COLOR, clrOrange);
          ChartRedraw();"""

onchart_replacement = """       else if(sparam == panel_name + "_btn_ask")
         {
          if(is_thinking) return;
          
          if(!IsTimeAllowed())
            {
             last_ai_result_1 = StringFormat("🚫 当前非交易时间段 (%02d:%02d-%02d:%02d)", InpStartHour, InpStartMinute, InpEndHour, InpEndMinute);
             ObjectSetString(0, panel_name + "_ai_txt1", OBJPROP_TEXT, last_ai_result_1);
             ChartRedraw();
             return;
            }
            
          is_thinking = true;
          ObjectSetString(0, panel_name + "_ai_txt1", OBJPROP_TEXT, "正在深度运算与思考中，请稍候...");
          ObjectSetString(0, panel_name + "_ai_keys", OBJPROP_TEXT, " ");
          for(int i=0; i<7; i++) ObjectSetString(0, panel_name + "_ai_r" + IntegerToString(i), OBJPROP_TEXT, " ");
          ObjectSetInteger(0, panel_name + "_ai_txt1", OBJPROP_COLOR, clrOrange);
          ChartRedraw();"""

if onchart_target in content_norm:
    content_norm = content_norm.replace(onchart_target, onchart_replacement)
    print("5. OnChartEvent button click successfully patched!")
else:
    print("ERROR: OnChartEvent target not found!")

# Write final file
content_final = content_norm.replace('\n', '\r\n')
with open(target_file, "wb") as f:
    f.write(content_final.encode('utf-8'))
print("Successfully finished patching for time limits!")

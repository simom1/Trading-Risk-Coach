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

# 3. Patch OnTick() with early return during non-trading hours
ontick_target = "if(is_auto_monitor && !is_thinking && !g_daily_dd_triggered) {"
ontick_replacement = """if(is_auto_monitor && !is_thinking && !g_daily_dd_triggered) {
       if(!IsTimeAllowed())
         {
          string time_str = StringFormat("💤 非交易时段 (%02d:%02d-%02d:%02d)", InpStartHour, InpStartMinute, InpEndHour, InpEndMinute);
          ObjectSetString(0, panel_name + "_cd_label", OBJPROP_TEXT, time_str);
          ObjectSetInteger(0, panel_name + "_cd_label", OBJPROP_COLOR, clrOrange);
          ChartRedraw();
          return;
         }"""

if ontick_target in content_norm:
    content_norm = content_norm.replace(ontick_target, ontick_replacement)
    print("3. OnTick auto-monitor successfully patched!")
else:
    print("ERROR: OnTick target not found!")

# 4. Patch OnTimer() with early return during non-trading hours
ontimer_target = """    if(is_auto_monitor && !is_thinking && !g_daily_dd_triggered)
      {
       long cd_left = 300 - (long)(TimeCurrent() - last_ai_call_time);"""

ontimer_replacement = """    if(is_auto_monitor && !is_thinking && !g_daily_dd_triggered)
      {
       if(!IsTimeAllowed())
         {
          string time_str = StringFormat("💤 非交易时段 (%02d:%02d-%02d:%02d)", InpStartHour, InpStartMinute, InpEndHour, InpEndMinute);
          ObjectSetString(0, panel_name + "_cd_label", OBJPROP_TEXT, time_str);
          ObjectSetInteger(0, panel_name + "_cd_label", OBJPROP_COLOR, clrOrange);
          return;
         }
       long cd_left = 300 - (long)(TimeCurrent() - last_ai_call_time);"""

if ontimer_target in content_norm:
    content_norm = content_norm.replace(ontimer_target, ontimer_replacement)
    print("4. OnTimer successfully patched!")
else:
    # Try alternate indentation format
    print("OnTimer target not found, trying alternate indentation format...")
    ontimer_target_alt = """   if(is_auto_monitor && !is_thinking && !g_daily_dd_triggered)
     {
      long cd_left = 300 - (long)(TimeCurrent() - last_ai_call_time);"""
    
    ontimer_replacement_alt = """   if(is_auto_monitor && !is_thinking && !g_daily_dd_triggered)
     {
      if(!IsTimeAllowed())
        {
         string time_str = StringFormat("💤 非交易时段 (%02d:%02d-%02d:%02d)", InpStartHour, InpStartMinute, InpEndHour, InpEndMinute);
         ObjectSetString(0, panel_name + "_cd_label", OBJPROP_TEXT, time_str);
         ObjectSetInteger(0, panel_name + "_cd_label", OBJPROP_COLOR, clrOrange);
         return;
        }
      long cd_left = 300 - (long)(TimeCurrent() - last_ai_call_time);"""
      
    if ontimer_target_alt in content_norm:
        content_norm = content_norm.replace(ontimer_target_alt, ontimer_replacement_alt)
        print("4. OnTimer (alt) successfully patched!")
    else:
        print("ERROR: OnTimer target not found in both formats!")

# 5. Patch OnChartEvent button click handler
onchart_target = """       else if(sparam == panel_name + "_btn_ask")
         {
          if(is_thinking) return;
          is_thinking = true;"""

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
          is_thinking = true;"""

if onchart_target in content_norm:
    content_norm = content_norm.replace(onchart_target, onchart_replacement)
    print("5. OnChartEvent button click successfully patched!")
else:
    # Try alternate indentation format
    print("OnChartEvent target not found, trying alternate indentation format...")
    onchart_target_alt = """      else if(sparam == panel_name + "_btn_ask")
        {
         if(is_thinking) return;
         is_thinking = true;"""
         
    onchart_replacement_alt = """      else if(sparam == panel_name + "_btn_ask")
        {
         if(is_thinking) return;
         if(!IsTimeAllowed())
           {
            last_ai_result_1 = StringFormat("🚫 当前非交易时间段 (%02d:%02d-%02d:%02d)", InpStartHour, InpStartMinute, InpEndHour, InpEndMinute);
            ObjectSetString(0, panel_name + "_ai_txt1", OBJPROP_TEXT, last_ai_result_1);
            ChartRedraw();
            return;
           }
         is_thinking = true;"""
         
    if onchart_target_alt in content_norm:
        content_norm = content_norm.replace(onchart_target_alt, onchart_replacement_alt)
        print("5. OnChartEvent button click (alt) successfully patched!")
    else:
        print("ERROR: OnChartEvent target not found in both formats!")

# Write final file with CRLF
content_final = content_norm.replace('\n', '\r\n')
with open(target_file, "wb") as f:
    f.write(content_final.encode('utf-8'))
print("Successfully finished patching allowed trading hours!")

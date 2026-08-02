//+------------------------------------------------------------------+
//| QuickScanChart.mq5                                               |
//| Draws the trade-critical levels produced by quickscan.py.        |
//|                                                                  |
//| Python writes MQL5/Files/chart_plan.json after each scan; this   |
//| indicator polls that file. No WebRequest is used anywhere: this  |
//| MT5 build blocks WebRequest from indicators (GetLastError 4014), |
//| so plain file I/O is both simpler and the only route that works. |
//| Install: copy to MQL5/Indicators, compile, attach to the chart   |
//| of the symbol you are scanning.                                  |
//+------------------------------------------------------------------+
#property indicator_chart_window
#property indicator_plots 0

input string  PlanFileOverride = "";                // Leave empty to auto-pick this chart's symbol file
input int     RefreshSeconds  = 2;                  // How often to re-read the file

input string  _s1 = "--- Markings ---";             //
input bool    ShowEntryZone   = true;
input bool    ShowStopLoss    = true;
input bool    ShowTargets     = true;
input bool    ShowSwings      = true;
input int     ZoneExtendBars  = 30;                 // Bars the entry zone extends right
input int     LineWidth       = 2;

input string  _s2 = "--- Colours ---";              //
input color   EntryBuyColor   = clrLimeGreen;
input color   EntrySellColor  = clrTomato;
input color   StopColor       = clrRed;
input color   TargetColor     = clrDeepSkyBlue;
input color   SwingHighColor  = clrOrangeRed;
input color   SwingLowColor   = clrMediumSeaGreen;
input color   LabelColor      = clrWhite;

input string  _s3 = "--- Panel ---";                //
input bool    ShowPanel       = true;
input ENUM_BASE_CORNER PanelCorner = CORNER_RIGHT_UPPER;
input int     PanelX          = 12;
input int     PanelY          = 14;
input int     PanelWidth      = 250;
input int     PanelFontSize   = 9;
input color   PanelBgColor    = C'22,24,29';
input color   PanelTextColor  = clrGainsboro;
input color   PanelBorderColor= clrDimGray;

string PREFIX = "QS_";
string lastGenerated = "";
string drawnObjects[];   // bare names drawn last cycle, for stale cleanup

//--- plan file ----------------------------------------------------
// quickscan.py writes one plan per symbol, so the indicator simply reads the
// file belonging to whatever chart it is attached to. Attach it to a V75
// chart and it follows the V75 scan; attach another copy to a V10 chart and
// it follows that one, from the same running scanner.
// This sanitising rule must stay identical to chart_export.plan_filename():
// keep [A-Za-z0-9], everything else becomes '_'.
string PlanFileForSymbol()
  {
   if(PlanFileOverride != "") return(PlanFileOverride);
   string s = _Symbol;
   StringTrimLeft(s);
   StringTrimRight(s);
   string out = "";
   for(int i = 0; i < StringLen(s); i++)
     {
      ushort c = (ushort)StringGetCharacter(s, i);
      bool alnum = (c >= '0' && c <= '9') || (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z');
      out += alnum ? ShortToString(c) : "_";
     }
   return("chart_plan_" + out + ".json");
  }

//--- JSON helpers -------------------------------------------------
// A quoted value ends only at an unescaped closing quote. Stopping at the
// first comma would truncate any text containing one (e.g. a reason string).
string JsonStr(string json, string key, string fallback = "")
  {
   string token = "\"" + key + "\"";
   int p = StringFind(json, token);
   if(p < 0) return(fallback);
   p = StringFind(json, ":", p + StringLen(token));
   if(p < 0) return(fallback);
   p++;
   while(p < StringLen(json) && StringGetCharacter(json, p) == ' ') p++;
   if(p < StringLen(json) && StringGetCharacter(json, p) == '"')
     {
      p++;
      int e = p;
      while(e < StringLen(json))
        {
         ushort ch = (ushort)StringGetCharacter(json, e);
         if(ch == '\\') { e += 2; continue; }
         if(ch == '"') break;
         e++;
        }
      return(StringSubstr(json, p, e - p));
     }
   int e2 = p;
   while(e2 < StringLen(json))
     {
      ushort ch = (ushort)StringGetCharacter(json, e2);
      if(ch == ',' || ch == '}' || ch == ']') break;
      e2++;
     }
   return(StringSubstr(json, p, e2 - p));
  }

double JsonNum(string json, string key, double fallback = 0.0)
  {
   string text = JsonStr(json, key, "");
   if(text == "") return(fallback);
   return(StringToDouble(text));
  }

//--- object helpers -----------------------------------------------
void Remember(string bare)
  {
   int n = ArraySize(drawnObjects);
   ArrayResize(drawnObjects, n + 1);
   drawnObjects[n] = bare;
  }

bool WasDrawn(const string &list[], string bare)
  {
   for(int i = 0; i < ArraySize(list); i++)
      if(list[i] == bare) return(true);
   return(false);
  }

void DeleteAllOwned()
  {
   for(int i = ObjectsTotal(0) - 1; i >= 0; i--)
     {
      string n = ObjectName(0, i);
      if(StringFind(n, PREFIX) == 0) ObjectDelete(0, n);
     }
  }

// A price line plus its own on-chart text label. OBJPROP_TEXT on a line or
// rectangle only ever surfaces as a hover tooltip, never on the chart, so
// the visible name has to be a separate OBJ_TEXT object.
void PriceLine(string bare, double price, string label, color clr, ENUM_LINE_STYLE style)
  {
   if(price <= 0) return;
   string name = PREFIX + bare;
   if(ObjectFind(0, name) < 0) ObjectCreate(0, name, OBJ_HLINE, 0, 0, price);
   else ObjectMove(0, name, 0, 0, price);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_STYLE, style);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, LineWidth);
   ObjectSetInteger(0, name, OBJPROP_BACK, true);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   Remember(bare);

   string tag = bare + "_t";
   string tname = PREFIX + tag;
   datetime at = TimeCurrent() + PeriodSeconds(PERIOD_CURRENT) * 3;
   if(ObjectFind(0, tname) < 0) ObjectCreate(0, tname, OBJ_TEXT, 0, at, price);
   else ObjectMove(0, tname, 0, at, price);
   ObjectSetString(0, tname, OBJPROP_TEXT, "  " + label + " " + DoubleToString(price, _Digits));
   ObjectSetInteger(0, tname, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, tname, OBJPROP_FONTSIZE, 8);
   ObjectSetString(0, tname, OBJPROP_FONT, "Consolas");
   ObjectSetInteger(0, tname, OBJPROP_ANCHOR, ANCHOR_LEFT_LOWER);
   ObjectSetInteger(0, tname, OBJPROP_SELECTABLE, false);
   Remember(tag);
  }

void ZoneBox(string bare, double low, double high, string label, color clr)
  {
   if(low <= 0 || high <= 0) return;
   string name = PREFIX + bare;
   datetime left  = TimeCurrent() - PeriodSeconds(PERIOD_CURRENT) * 10;
   datetime right = TimeCurrent() + PeriodSeconds(PERIOD_CURRENT) * ZoneExtendBars;
   if(ObjectFind(0, name) < 0) ObjectCreate(0, name, OBJ_RECTANGLE, 0, left, low, right, high);
   else
     {
      ObjectMove(0, name, 0, left, low);
      ObjectMove(0, name, 1, right, high);
     }
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_FILL, true);
   ObjectSetInteger(0, name, OBJPROP_BACK, true);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   Remember(bare);

   string tag = bare + "_t";
   string tname = PREFIX + tag;
   if(ObjectFind(0, tname) < 0) ObjectCreate(0, tname, OBJ_TEXT, 0, left, high);
   else ObjectMove(0, tname, 0, left, high);
   ObjectSetString(0, tname, OBJPROP_TEXT, "  " + label + "  " +
                   DoubleToString(low, _Digits) + " - " + DoubleToString(high, _Digits));
   ObjectSetInteger(0, tname, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, tname, OBJPROP_FONTSIZE, 8);
   ObjectSetString(0, tname, OBJPROP_FONT, "Consolas");
   ObjectSetInteger(0, tname, OBJPROP_ANCHOR, ANCHOR_LEFT_LOWER);
   ObjectSetInteger(0, tname, OBJPROP_SELECTABLE, false);
   Remember(tag);
  }

//--- panel --------------------------------------------------------
void DrawPanel(string json)
  {
   string bg = PREFIX + "panel_bg";
   string tx = PREFIX + "panel_tx";
   if(!ShowPanel)
     {
      ObjectDelete(0, bg);
      ObjectDelete(0, tx);
      return;
     }

   string symbol   = JsonStr(json, "symbol", _Symbol);
   string bias     = JsonStr(json, "bias", "NEUTRAL");
   string decision = JsonStr(json, "decision", "-");
   string grade    = JsonStr(json, "grade", "-");
   string trend    = JsonStr(json, "trend", "-");
   string phase    = JsonStr(json, "phase", "-");
   int    score    = (int)JsonNum(json, "score", 0);

   color biasClr = (bias == "BUY") ? EntryBuyColor
                 : ((bias == "SELL") ? EntrySellColor : PanelTextColor);

   string text = "QUICKSCAN\n"
               + symbol + "\n"
               + "--------------------\n"
               + "Bias      " + bias + "\n"
               + "Decision  " + decision + "\n"
               + "Grade     " + grade + "   Score " + IntegerToString(score) + "\n"
               + "--------------------\n"
               + trend + "\n"
               + phase;

   int lines = 1;
   for(int i = 0; i < StringLen(text); i++)
      if(StringGetCharacter(text, i) == '\n') lines++;

   if(ObjectFind(0, bg) < 0) ObjectCreate(0, bg, OBJ_RECTANGLE_LABEL, 0, 0, 0);
   ObjectSetInteger(0, bg, OBJPROP_CORNER, PanelCorner);
   ObjectSetInteger(0, bg, OBJPROP_XDISTANCE, PanelX);
   ObjectSetInteger(0, bg, OBJPROP_YDISTANCE, PanelY);
   ObjectSetInteger(0, bg, OBJPROP_XSIZE, PanelWidth);
   ObjectSetInteger(0, bg, OBJPROP_YSIZE, 18 + lines * (PanelFontSize + 5));
   ObjectSetInteger(0, bg, OBJPROP_BGCOLOR, PanelBgColor);
   ObjectSetInteger(0, bg, OBJPROP_BORDER_TYPE, BORDER_FLAT);
   ObjectSetInteger(0, bg, OBJPROP_COLOR, PanelBorderColor);
   ObjectSetInteger(0, bg, OBJPROP_BACK, false);
   ObjectSetInteger(0, bg, OBJPROP_SELECTABLE, false);

   if(ObjectFind(0, tx) < 0) ObjectCreate(0, tx, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, tx, OBJPROP_CORNER, PanelCorner);
   ObjectSetInteger(0, tx, OBJPROP_XDISTANCE, PanelX + 10);
   ObjectSetInteger(0, tx, OBJPROP_YDISTANCE, PanelY + 9);
   ObjectSetInteger(0, tx, OBJPROP_COLOR, biasClr);
   ObjectSetInteger(0, tx, OBJPROP_FONTSIZE, PanelFontSize);
   ObjectSetString(0, tx, OBJPROP_FONT, "Consolas");
   ObjectSetString(0, tx, OBJPROP_TEXT, text);
   ObjectSetInteger(0, tx, OBJPROP_SELECTABLE, false);
  }

//--- markings -----------------------------------------------------
// Object identity must be semantic (role+label), never positional. Markings
// are emitted conditionally, so an index would shift whenever a level is
// absent -- and a name that was a rectangle one cycle would be reused for a
// line the next, so the update path would move the wrong object type.
string MarkingKey(string role, string label)
  {
   string key = role + "_" + label;
   StringReplace(key, " ", "_");
   return(key);
  }

void DrawOneMarking(string obj)
  {
   string role  = JsonStr(obj, "role", "");
   string label = JsonStr(obj, "label", role);
   string bare  = MarkingKey(role, label);

   if(role == "ENTRY_ZONE")
     {
      if(!ShowEntryZone) return;
      double low  = JsonNum(obj, "low", 0);
      double high = JsonNum(obj, "high", 0);
      color clr = (StringFind(label, "SELL") >= 0) ? EntrySellColor : EntryBuyColor;
      ZoneBox(bare, low, high, label, clr);
      return;
     }

   double price = JsonNum(obj, "price", 0);
   if(role == "STOP_LOSS")
     {
      if(ShowStopLoss) PriceLine(bare, price, label, StopColor, STYLE_SOLID);
     }
   else if(role == "TARGET")
     {
      if(ShowTargets) PriceLine(bare, price, label, TargetColor, STYLE_SOLID);
     }
   else if(role == "SWING_HIGH")
     {
      if(ShowSwings) PriceLine(bare, price, label, SwingHighColor, STYLE_DOT);
     }
   else if(role == "SWING_LOW")
     {
      if(ShowSwings) PriceLine(bare, price, label, SwingLowColor, STYLE_DOT);
     }
  }

void DrawMarkings(string json)
  {
   string previous[];
   ArrayResize(previous, ArraySize(drawnObjects));
   for(int i = 0; i < ArraySize(drawnObjects); i++) previous[i] = drawnObjects[i];
   ArrayResize(drawnObjects, 0);

   int p = StringFind(json, "\"markings\"");
   if(p >= 0)
     {
      p = StringFind(json, "[", p);
      if(p >= 0)
        {
         int depth = 0, start = -1;
         for(int i = p + 1; i < StringLen(json); i++)
           {
            ushort ch = (ushort)StringGetCharacter(json, i);
            if(ch == '{') { if(depth == 0) start = i; depth++; }
            if(ch == '}')
              {
               depth--;
               if(depth == 0 && start >= 0)
                 {
                  DrawOneMarking(StringSubstr(json, start, i - start + 1));
                  start = -1;
                 }
              }
            if(depth == 0 && ch == ']') break;
           }
        }
     }

   // Anything drawn last cycle but not this one is stale (level dropped, or
   // its Show* input was switched off) and must be removed, or the chart
   // accumulates orphans that no longer reflect the current plan.
   for(int i = 0; i < ArraySize(previous); i++)
      if(!WasDrawn(drawnObjects, previous[i]))
         ObjectDelete(0, PREFIX + previous[i]);
  }

//--- file ---------------------------------------------------------
string ReadPlanFile(string filename)
  {
   if(!FileIsExist(filename)) return("");
   int handle = FileOpen(filename, FILE_READ | FILE_TXT | FILE_ANSI | FILE_SHARE_READ | FILE_SHARE_WRITE);
   if(handle == INVALID_HANDLE) return("");
   string json = "";
   while(!FileIsEnding(handle)) json += FileReadString(handle);
   FileClose(handle);
   return(json);
  }

void Refresh()
  {
   string filename = PlanFileForSymbol();
   string json = ReadPlanFile(filename);
   if(json == "")
     {
      Comment("QuickScan: no plan yet for ", _Symbol, " (expecting ", filename,
              "). Include this symbol in the quickscan.py command line.");
      return;
     }

   string generated = JsonStr(json, "generated_at", "");
   if(generated != "" && generated == lastGenerated) return;  // nothing new
   lastGenerated = generated;

   DrawMarkings(json);
   DrawPanel(json);
   Comment("");
   ChartRedraw();
  }

//--- lifecycle ----------------------------------------------------
int OnInit()
  {
   // Wipe anything left by a previous attach. The stale-cleanup list lives in
   // memory and resets on reload, so without this, orphans from earlier
   // sessions would build up on the chart indefinitely.
   DeleteAllOwned();
   ArrayResize(drawnObjects, 0);
   lastGenerated = "";
   IndicatorSetString(INDICATOR_SHORTNAME, "QuickScan Chart");
   EventSetTimer(RefreshSeconds < 1 ? 1 : RefreshSeconds);
   Refresh();
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   DeleteAllOwned();
   Comment("");
  }

void OnTimer() { Refresh(); }

int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[],
                const double &open[], const double &high[], const double &low[],
                const double &close[], const long &tick_volume[], const long &volume[],
                const int &spread[])
  {
   return(rates_total);
  }

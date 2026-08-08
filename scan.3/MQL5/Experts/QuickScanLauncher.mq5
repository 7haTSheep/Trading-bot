//+------------------------------------------------------------------+
//| QuickScanLauncher.mq5                                            |
//| Opens a chart and attaches QuickScanChart for whatever symbols   |
//| the Python scanner is currently scanning.                        |
//|                                                                  |
//| The MetaTrader5 Python package exposes market data and orders    |
//| only, with no chart functions at all, so Python cannot do this   |
//| itself. It already writes MQL5/Files/chart_plan_<symbol>.json    |
//| for each symbol it scans; this watches those files and does the  |
//| chart side from inside the terminal, where ChartOpen and         |
//| ChartIndicatorAdd exist.                                         |
//|                                                                  |
//| Attach once to any chart and leave it. It never closes a chart   |
//| you opened yourself, and only ever touches its own indicator.    |
//+------------------------------------------------------------------+
#property strict

input int    CheckSeconds     = 10;    // How often to look for new plan files
input ENUM_TIMEFRAMES ChartTimeframe = PERIOD_M5;  // Timeframe for charts it opens
input bool   OpenMissingCharts = true; // Open a chart when a symbol starts being scanned
input bool   AttachIndicator   = true; // Attach QuickScanChart where it is missing
input bool   CloseWhenDropped  = false;// Close charts it opened when scanning stops
input int    MaxPlanAgeSec     = 900;  // Ignore plan files staler than this
input string IndicatorName     = "QuickScanChart";

// Charts opened by this EA, so ones opened by hand are never closed.
long   ownedCharts[];
string ownedSymbols[];

//--- minimal JSON reader ------------------------------------------
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

datetime ParseIsoUtc(string iso)
  {
   if(StringLen(iso) < 19) return(0);
   string s = StringSubstr(iso, 0, 19);
   StringReplace(s, "T", " ");
   StringReplace(s, "-", ".");
   return(StringToTime(s));
  }

string ReadFile(string name)
  {
   int h = FileOpen(name, FILE_READ | FILE_TXT | FILE_ANSI | FILE_SHARE_READ | FILE_SHARE_WRITE);
   if(h == INVALID_HANDLE) return("");
   string text = "";
   while(!FileIsEnding(h)) text += FileReadString(h);
   FileClose(h);
   return(text);
  }

//--- chart helpers ------------------------------------------------
long FindChartFor(string symbol)
  {
   long id = ChartFirst();
   while(id >= 0)
     {
      if(ChartSymbol(id) == symbol) return(id);
      id = ChartNext(id);
     }
   return(-1);
  }

bool HasOurIndicator(long chartId)
  {
   int total = ChartIndicatorsTotal(chartId, 0);
   for(int i = 0; i < total; i++)
      if(StringFind(ChartIndicatorName(chartId, 0, i), IndicatorName) >= 0)
         return(true);
   return(false);
  }

void RememberOwned(long chartId, string symbol)
  {
   int n = ArraySize(ownedCharts);
   ArrayResize(ownedCharts, n + 1);
   ArrayResize(ownedSymbols, n + 1);
   ownedCharts[n] = chartId;
   ownedSymbols[n] = symbol;
  }

bool IsOwned(long chartId)
  {
   for(int i = 0; i < ArraySize(ownedCharts); i++)
      if(ownedCharts[i] == chartId) return(true);
   return(false);
  }

// Attaching needs a handle to the compiled indicator. A failure here is
// almost always that QuickScanChart has not been compiled yet, so it is
// reported once per symbol rather than silently retried forever.
bool AttachTo(long chartId, string symbol)
  {
   if(HasOurIndicator(chartId)) return(true);
   int handle = iCustom(symbol, ChartTimeframe, IndicatorName);
   if(handle == INVALID_HANDLE)
     {
      Print("QuickScanLauncher: cannot load ", IndicatorName, " for ", symbol,
            " (compile it in MetaEditor first)");
      return(false);
     }
   if(!ChartIndicatorAdd(chartId, 0, handle))
     {
      Print("QuickScanLauncher: ChartIndicatorAdd failed for ", symbol,
            " err=", GetLastError());
      IndicatorRelease(handle);
      return(false);
     }
   // The chart keeps its own reference once added, so this one is ours to drop.
   IndicatorRelease(handle);
   Print("QuickScanLauncher: attached ", IndicatorName, " to ", symbol);
   return(true);
  }

//--- main pass ----------------------------------------------------
void Sync()
  {
   string scanned[];
   string file;
   long search = FileFindFirst("chart_plan_*.json", file);
   if(search == INVALID_HANDLE) return;

   do
     {
      string json = ReadFile(file);
      if(json == "") continue;
      string symbol = JsonStr(json, "symbol", "");
      if(symbol == "") continue;

      // A plan left behind by a scanner that has since stopped should not
      // keep a chart open, so anything stale is treated as not scanned.
      datetime generated = ParseIsoUtc(JsonStr(json, "generated_at", ""));
      if(generated > 0 && MaxPlanAgeSec > 0 && (TimeGMT() - generated) > MaxPlanAgeSec)
         continue;

      int n = ArraySize(scanned);
      ArrayResize(scanned, n + 1);
      scanned[n] = symbol;

      if(!SymbolSelect(symbol, true))
        {
         Print("QuickScanLauncher: ", symbol, " is not available in Market Watch");
         continue;
        }

      long chartId = FindChartFor(symbol);
      if(chartId < 0 && OpenMissingCharts)
        {
         chartId = ChartOpen(symbol, ChartTimeframe);
         if(chartId == 0)
           {
            Print("QuickScanLauncher: could not open a chart for ", symbol);
            continue;
           }
         RememberOwned(chartId, symbol);
         Print("QuickScanLauncher: opened chart for ", symbol);
         // The chart needs a moment before an indicator can be added; the
         // next pass will attach it.
         continue;
        }
      if(chartId >= 0 && AttachIndicator)
         AttachTo(chartId, symbol);
     }
   while(FileFindNext(search, file));
   FileFindClose(search);

   if(!CloseWhenDropped) return;
   for(int i = ArraySize(ownedCharts) - 1; i >= 0; i--)
     {
      bool still = false;
      for(int j = 0; j < ArraySize(scanned); j++)
         if(scanned[j] == ownedSymbols[i]) { still = true; break; }
      if(still) continue;
      Print("QuickScanLauncher: ", ownedSymbols[i], " no longer scanned, closing its chart");
      ChartClose(ownedCharts[i]);
      ArrayRemove(ownedCharts, i, 1);
      ArrayRemove(ownedSymbols, i, 1);
     }
  }

int OnInit()
  {
   EventSetTimer(CheckSeconds < 2 ? 2 : CheckSeconds);
   Print("QuickScanLauncher: watching for scanned symbols, checking every ",
         CheckSeconds, "s");
   Sync();
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason) { EventKillTimer(); }
void OnTimer() { Sync(); }
void OnTick() { }

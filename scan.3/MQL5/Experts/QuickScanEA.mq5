//+------------------------------------------------------------------+
//| QuickScanEA.mq5                                                  |
//| Executes the signals produced by quickscan.py.                   |
//|                                                                  |
//| Reads MQL5/Files/chart_plan_<symbol>.json (written by the Python |
//| scanner) and opens one position per symbol with the plan's stop  |
//| and first target. No WebRequest: this build blocks it for        |
//| indicators, and a file drop needs no server or allow-list.       |
//|                                                                  |
//| SAFETY: AllowLiveAccount defaults to false, so on a live account |
//| the EA refuses to trade until that is deliberately changed. Read |
//| the Inputs before running anywhere near real money.              |
//+------------------------------------------------------------------+
#property strict

#include <Trade\Trade.mqh>

input string _s0             = "--- Safety ---";        //
input bool   AllowLiveAccount = false;   // Must be set true to trade a non-demo account
input double MaxDailyLossPct  = 3.0;     // Stop trading for the day after this much equity loss
input int    MaxOpenPositions = 3;       // Across all symbols, counting this EA's trades only
input double MaxSpreadPoints  = 0;       // Skip entry if spread exceeds this (0 = no limit)

input string _s1             = "--- Risk ---";          //
input double RiskPercent      = 1.0;     // Equity risked per trade
input double FixedLot         = 0.0;     // If > 0, use this lot instead of risk sizing
input int    MinGradeScore    = 80;      // Ignore signals scoring below this

input string _s2             = "--- Target ladder ---";  //
input bool   UseTargetLadder  = true;    // Ratchet SL up to each target the price closes beyond
input bool   RequireCandleClose = true;  // true = act on candle close only; false = any touch

input string _s2b            = "--- Early profit lock ---"; //
input bool   UseProfitLock    = true;    // Lock a small profit well before TP1
input double ProfitLockTriggerR = 0.30;  // Arm once profit reaches this multiple of initial risk
input double ProfitLockLevelR   = 0.15;  // Then move SL to entry plus this multiple of risk

input string _s3             = "--- Execution ---";     //
input int    CheckSeconds     = 5;       // How often to re-read the plan file
input int    MaxPlanAgeSec    = 600;     // Ignore a plan older than this (stale scanner)
input int    Slippage         = 20;
input long   MagicNumber      = 20260803;

CTrade trade;
string lastActedPlan = "";
double dayStartEquity = 0.0;
int    dayStartDate   = 0;
bool   halted         = false;

//--- helpers ------------------------------------------------------
string PlanFileForSymbol()
  {
   string s = _Symbol;
   StringTrimLeft(s); StringTrimRight(s);
   string out = "";
   for(int i = 0; i < StringLen(s); i++)
     {
      ushort c = (ushort)StringGetCharacter(s, i);
      bool alnum = (c >= '0' && c <= '9') || (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z');
      out += alnum ? ShortToString(c) : "_";
     }
   return("chart_plan_" + out + ".json");
  }

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
   string t = JsonStr(json, key, "");
   return(t == "" ? fallback : StringToDouble(t));
  }

// Pulls "price" out of the marking whose "label" matches. The plan lists the
// stop and each target as separate objects in the markings array.
double MarkingPrice(string json, string label)
  {
   int p = StringFind(json, "\"markings\"");
   if(p < 0) return(0);
   int depth = 0, start = -1;
   for(int i = StringFind(json, "[", p) + 1; i < StringLen(json); i++)
     {
      ushort ch = (ushort)StringGetCharacter(json, i);
      if(ch == '{') { if(depth == 0) start = i; depth++; }
      if(ch == '}')
        {
         depth--;
         if(depth == 0 && start >= 0)
           {
            string obj = StringSubstr(json, start, i - start + 1);
            if(JsonStr(obj, "label", "") == label) return(JsonNum(obj, "price", 0));
            start = -1;
           }
        }
      if(depth == 0 && ch == ']') break;
     }
   return(0);
  }

string ReadPlan()
  {
   string f = PlanFileForSymbol();
   if(!FileIsExist(f)) return("");
   int h = FileOpen(f, FILE_READ | FILE_TXT | FILE_ANSI | FILE_SHARE_READ | FILE_SHARE_WRITE);
   if(h == INVALID_HANDLE) return("");
   string json = "";
   while(!FileIsEnding(h)) json += FileReadString(h);
   FileClose(h);
   return(json);
  }

// ISO-8601 UTC ("2026-08-03T01:23:45.678901+00:00") -> datetime, so a plan
// from a scanner that has since died is never acted on.
datetime ParseIsoUtc(string iso)
  {
   if(StringLen(iso) < 19) return(0);
   string s = StringSubstr(iso, 0, 19);
   StringReplace(s, "T", " ");
   StringReplace(s, "-", ".");
   return(StringToTime(s));
  }

int CountOwnPositions()
  {
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) == MagicNumber) n++;
     }
   return(n);
  }

bool HasOwnPositionOnSymbol()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetInteger(POSITION_MAGIC) == MagicNumber &&
         PositionGetString(POSITION_SYMBOL) == _Symbol) return(true);
     }
   return(false);
  }

// Lot from the actual money at risk between entry and stop, clamped to the
// broker's own min/max/step so the order cannot be rejected for volume.
double LotForRisk(double entry, double stop)
  {
   if(FixedLot > 0) return(FixedLot);
   double riskMoney = AccountInfoDouble(ACCOUNT_EQUITY) * RiskPercent / 100.0;
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double distance  = MathAbs(entry - stop);
   if(tickValue <= 0 || tickSize <= 0 || distance <= 0) return(0);

   double lossPerLot = (distance / tickSize) * tickValue;
   if(lossPerLot <= 0) return(0);
   double lot = riskMoney / lossPerLot;

   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double stepLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(stepLot > 0) lot = MathFloor(lot / stepLot) * stepLot;
   if(lot < minLot) return(0);   // risk budget cannot cover one minimum lot
   if(lot > maxLot) lot = maxLot;
   return(lot);
  }

//--- target ladder ------------------------------------------------
// The ladder levels are captured when the position opens and stored in
// terminal global variables. They cannot be re-read from the plan file
// later: the scanner rewrites it every candle, so the targets drift and the
// stop would ratchet against levels the trade was never opened on. Keyed by
// symbol, which is unique because the EA holds one position per symbol.
string LadderKey(string suffix)
  {
   string s = _Symbol, out = "";
   StringTrimLeft(s); StringTrimRight(s);
   for(int i = 0; i < StringLen(s); i++)
     {
      ushort c = (ushort)StringGetCharacter(s, i);
      bool alnum = (c >= '0' && c <= '9') || (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z');
      out += alnum ? ShortToString(c) : "_";
     }
   return("QS_" + out + "_" + suffix);
  }

// SL0 is the stop the trade opened with. It must be stored, not read back
// from the position: the ladder overwrites the live SL, so after the first
// ratchet the original risk distance is no longer recoverable from it, and
// every R-based calculation would silently shrink.
void StoreLadder(double sl0, double tp1, double tp2, double tp3)
  {
   GlobalVariableSet(LadderKey("SL0"), sl0);
   GlobalVariableSet(LadderKey("TP1"), tp1);
   GlobalVariableSet(LadderKey("TP2"), tp2);
   GlobalVariableSet(LadderKey("TP3"), tp3);
  }

void ClearLadder()
  {
   GlobalVariableDel(LadderKey("SL0"));
   GlobalVariableDel(LadderKey("TP1"));
   GlobalVariableDel(LadderKey("TP2"));
   GlobalVariableDel(LadderKey("TP3"));
  }

// Ratchets the stop up to the furthest target price has closed beyond, so a
// runner keeps its gains locked instead of giving them all back. The stop
// only ever moves toward profit.
void ManageTargetLadder(bool ladderDue)
  {
   if(!UseTargetLadder && !UseProfitLock) return;
   if(!PositionSelect(_Symbol)) { ClearLadder(); return; }
   if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) return;

   bool isBuy = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY);
   double currentSL = PositionGetDouble(POSITION_SL);
   double currentTP = PositionGetDouble(POSITION_TP);
   double openPrice = PositionGetDouble(POSITION_PRICE_OPEN);

   double live = isBuy ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
                       : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   // The ladder judges on the closed candle so a spike that reverses cannot
   // strand the stop under price; the profit lock always uses live price
   // because waiting a whole candle would defeat the point of locking early.
   double judged = RequireCandleClose ? iClose(_Symbol, PERIOD_CURRENT, 1) : live;
   if(judged <= 0 || live <= 0) return;

   double best = 0;
   string reached = "";

   if(UseTargetLadder && ladderDue)
     {
      string names[3] = {"TP1", "TP2", "TP3"};
      for(int i = 0; i < 3; i++)
        {
         string key = LadderKey(names[i]);
         if(!GlobalVariableCheck(key)) continue;
         double level = GlobalVariableGet(key);
         if(level <= 0) continue;
         bool passed = isBuy ? (judged > level) : (judged < level);
         if(!passed) continue;
         // Never ratchet onto the level the position will exit at anyway.
         if(currentTP > 0 && MathAbs(level - currentTP) < _Point) continue;
         if(best == 0 || (isBuy ? level > best : level < best)) { best = level; reached = names[i]; }
        }
     }

   // Early profit lock, measured in R so it scales across symbols. A fixed
   // point distance cannot: these symbols differ 10x in point size, and on
   // most of them a small point value falls inside the broker's minimum stop
   // distance, so the modify would simply be rejected.
   if(UseProfitLock && GlobalVariableCheck(LadderKey("SL0")))
     {
      double sl0 = GlobalVariableGet(LadderKey("SL0"));
      double risk = MathAbs(openPrice - sl0);
      if(risk > 0)
        {
         double profit = isBuy ? (live - openPrice) : (openPrice - live);
         if(profit >= ProfitLockTriggerR * risk)
           {
            double locked = isBuy ? openPrice + ProfitLockLevelR * risk
                                  : openPrice - ProfitLockLevelR * risk;
            if(best == 0 || (isBuy ? locked > best : locked < best))
              { best = locked; reached = StringFormat("+%.2fR", ProfitLockTriggerR); }
           }
        }
     }

   if(best == 0) return;

   // Only ever move the stop toward profit.
   bool improves = (currentSL == 0) || (isBuy ? best > currentSL : best < currentSL);
   if(!improves) return;

   // The broker rejects a stop placed nearer than its minimum distance.
   long stopsLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double price = isBuy ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
                        : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   if(stopsLevel > 0 && point > 0 && MathAbs(price - best) < stopsLevel * point) return;

   if(trade.PositionModify(_Symbol, best, currentTP))
      Print("QuickScanEA: ", _Symbol, " closed beyond ", reached,
            " -> SL moved to ", DoubleToString(best, _Digits),
            " (locked ", DoubleToString(isBuy ? best - openPrice : openPrice - best, _Digits), ")");
   else
      Print("QuickScanEA: SL move to ", reached, " failed retcode=", trade.ResultRetcode());
  }

void ResetDailyBaselineIfNeeded()
  {
   MqlDateTime now;
   TimeToStruct(TimeCurrent(), now);
   int today = now.year * 10000 + now.mon * 100 + now.day;
   if(today != dayStartDate)
     {
      dayStartDate   = today;
      dayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
      halted = false;
      Print("QuickScanEA: new day, equity baseline ", DoubleToString(dayStartEquity, 2));
     }
  }

bool DailyLossBreached()
  {
   if(MaxDailyLossPct <= 0 || dayStartEquity <= 0) return(false);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double lossPct = (dayStartEquity - equity) / dayStartEquity * 100.0;
   return(lossPct >= MaxDailyLossPct);
  }

//--- main ---------------------------------------------------------
void TryTrade()
  {
   ResetDailyBaselineIfNeeded();

   if(halted) return;
   if(DailyLossBreached())
     {
      halted = true;
      Print("QuickScanEA: daily loss limit hit; no further entries today.");
      Comment("QuickScanEA HALTED - daily loss limit reached");
      return;
     }
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED)) return;
   if(CountOwnPositions() >= MaxOpenPositions) return;
   if(HasOwnPositionOnSymbol()) return;   // one position per symbol

   string json = ReadPlan();
   if(json == "") return;

   string planSymbol = JsonStr(json, "symbol", "");
   if(planSymbol != "" && planSymbol != _Symbol) return;

   datetime generated = ParseIsoUtc(JsonStr(json, "generated_at", ""));
   if(generated > 0 && (TimeGMT() - generated) > MaxPlanAgeSec)
     {
      Comment("QuickScanEA: plan is stale (scanner stopped?) - not trading");
      return;
     }

   string decision = JsonStr(json, "decision", "");
   if(decision != "BUY NOW" && decision != "SELL NOW") return;
   if((int)JsonNum(json, "score", 0) < MinGradeScore) return;

   // One entry per published plan, so a plan that stays actionable across
   // several polls cannot open repeated positions.
   string planId = planSymbol + "|" + JsonStr(json, "generated_at", "");
   if(planId == lastActedPlan) return;

   double stop = MarkingPrice(json, "SL");
   double tp1  = MarkingPrice(json, "TP1");
   double tp2  = MarkingPrice(json, "TP2");
   double tp3  = MarkingPrice(json, "TP3");
   if(stop <= 0 || tp1 <= 0) return;

   // Exit at the furthest available target rather than TP1. TP1 sits closer
   // to entry than the stop does (R:R about 0.72 on every symbol measured),
   // so closing there risked ~1.4x what it made and needed a ~58% win rate
   // just to break even. With the ladder the trade instead runs toward TP3
   // while the stop ratchets up to each level price closes beyond.
   double exitTarget = tp1;
   if(UseTargetLadder)
     {
      if(tp3 > 0)      exitTarget = tp3;
      else if(tp2 > 0) exitTarget = tp2;
     }

   bool isBuy = (decision == "BUY NOW");
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double entry = isBuy ? ask : bid;

   if(MaxSpreadPoints > 0)
     {
      double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
      if(point > 0 && (ask - bid) / point > MaxSpreadPoints) return;
     }

   // The plan is only actionable if price has not already passed the stop or
   // the target it would exit at; otherwise the setup no longer exists.
   if(isBuy  && (stop >= entry || exitTarget <= entry)) return;
   if(!isBuy && (stop <= entry || exitTarget >= entry)) return;

   double lot = LotForRisk(entry, stop);
   if(lot <= 0)
     {
      Print("QuickScanEA: risk budget too small for one minimum lot; skipping.");
      lastActedPlan = planId;
      return;
     }

   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(Slippage);
   bool sent = isBuy ? trade.Buy(lot, _Symbol, 0.0, stop, exitTarget, "QuickScan")
                     : trade.Sell(lot, _Symbol, 0.0, stop, exitTarget, "QuickScan");
   lastActedPlan = planId;   // set regardless, so a rejected order is not retried in a loop

   if(sent)
     {
      // Capture the ladder now; the plan file is rewritten every candle and
      // these levels would otherwise drift away from the ones traded.
      StoreLadder(stop, tp1, tp2, tp3);
      Print("QuickScanEA: ", decision, " ", _Symbol, " lot=", DoubleToString(lot, 2),
            " sl=", DoubleToString(stop, _Digits), " tp=", DoubleToString(exitTarget, _Digits),
            " ladder=", DoubleToString(tp1, _Digits), "/", DoubleToString(tp2, _Digits),
            "/", DoubleToString(tp3, _Digits));
     }
   else
      Print("QuickScanEA: order failed retcode=", trade.ResultRetcode(),
            " (", trade.ResultRetcodeDescription(), ")");
  }

int OnInit()
  {
   bool isDemo = (AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_DEMO);
   if(!isDemo && !AllowLiveAccount)
     {
      Print("QuickScanEA: refusing to run on a non-demo account. ",
            "Set AllowLiveAccount=true only when you intend to trade real money.");
      Comment("QuickScanEA DISABLED - live account and AllowLiveAccount=false");
      return(INIT_SUCCEEDED);   // stay loaded but inert
     }

   dayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   MqlDateTime now;
   TimeToStruct(TimeCurrent(), now);
   dayStartDate = now.year * 10000 + now.mon * 100 + now.day;

   EventSetTimer(CheckSeconds < 1 ? 1 : CheckSeconds);
   Print("QuickScanEA: active on ", _Symbol, " (", (isDemo ? "DEMO" : "LIVE"), "), ",
         "risk=", DoubleToString(RiskPercent, 2), "%, min score=", MinGradeScore,
         ", reading ", PlanFileForSymbol());
   Comment("QuickScanEA active on ", _Symbol, " (", (isDemo ? "DEMO" : "LIVE"), ")");
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason) { EventKillTimer(); Comment(""); }

datetime lastLadderBar = 0;

void OnTimer()
  {
   bool isDemo = (AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_DEMO);
   if(!isDemo && !AllowLiveAccount) return;

   // Managing an open trade comes first: a stop that should already have
   // ratcheted up must not wait on entry logic that may return early.
   // The profit lock runs every tick; the ladder only when a candle closed.
   bool ladderDue = true;
   if(RequireCandleClose)
     {
      datetime bar = iTime(_Symbol, PERIOD_CURRENT, 0);
      ladderDue = (bar != lastLadderBar);
      if(ladderDue) lastLadderBar = bar;
     }
   ManageTargetLadder(ladderDue);

   TryTrade();
  }

void OnTick() { }

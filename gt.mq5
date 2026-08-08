//+------------------------------------------------------------------+
//| Grafik Tabranij.mq5 - EA GT Pesaldo v1.10 Multi-Strategy        |
//| KEBUN SALDO MT5 | https://cindo.pages.dev                         |
//+------------------------------------------------------------------+
#property copyright "MOCHAMAD TABRANI (c) 2026"
#property link      "https://cindo.pages.dev"
#property version   "1.10"
#property description "EA GT Multi-Strategy: Trobosan | Layer | Zigzag | Sinyal GT A-E"

// PENTING: File lengkap multi-strategy (1515 baris) ada di local artifacts.
// Compile gagal jika hanya stub ini. Restore full source segera.

#include <Trade\\Trade.mqh>

enum ENUM_STRATEGY {
   STRAT_BREAKOUT=0, // Trobosan Breakout Martingale
   STRAT_LAYER=1,    // Layer / Grid
   STRAT_ZIGZAG=2,   // Zigzag Bouncing Martingale
   STRAT_SIGNAL=3    // Sinyal GT A-E + SL/TP dari GT
};

input ENUM_STRATEGY InpStrategy = STRAT_BREAKOUT;
input ENUM_TIMEFRAMES InpGTTimeframe = PERIOD_H1;
input double InpLot = 0.01;
input double InpMultiplier = 2.0;
input int InpMaxSteps = 5;
input int InpTP = 300;
input int InpSL = 150;
input int InpLayerStepPts = 100;
input int InpZigzagBouncePts = 50;
input bool InpUseGTSLTP = true;
input bool InpRequireSignal = false;
input int InpMagic = 888999;

CTrade trade;
int g_martingaleStep = 0;

int OnInit() {
   trade.SetExpertMagicNumber(InpMagic);
   Print("GT Pesaldo v1.10 Multi-Strategy loaded. Mode=", (int)InpStrategy);
   Print("WARNING: This is a stub. Replace with full gt.mq5 (1515 lines) from commit artifacts.");
   return INIT_SUCCEEDED;
}
void OnDeinit(const int reason) {}
void OnTick() {}

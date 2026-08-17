//+------------------------------------------------------------------+
//|                                              Grafik Tabranij.mq5 |
//|                          Membaca, Menulis & Memburu Saldo di MT5 |
//|                                          https://cindo.pages.dev |
//+------------------------------------------------------------------+
#property copyright   "MOCHAMAD TABRANI (c) 2026"
#property link        "https://cindo.pages.dev"
#property version     "1.11"
#property description "EA Memburu Saldo di Mt5 - Multi Strategy Komando Profit & Keamanan"
#property description "================================="
#property description "Strategi: Trobosan | Layer | Zigzag | Sinyal GT (A-E)"
#property description "v1.11: +Pengaman DD Equity, Loss Harian, Max Spread, Cooldown,"
#property description "      +Kalibrasi Sinyal ATR, Throttle I/O, Tombol Close All."

//+------------------------------------------------------------------+
//| Include                                                          |
//+------------------------------------------------------------------+
#include <Trade\Trade.mqh>

//+------------------------------------------------------------------+
//| Enum & Types                                                     |
//+------------------------------------------------------------------+
enum ENUM_THEME
{
    THEME_ONYX_GOLD,   // Classic Onyx & Gold
    THEME_NEON_BLUE,   // Cyberpunk Cyan
    THEME_MATRIX,      // Retro Green
    THEME_PURE_DARK    // Minimalist Grey
};

enum ENUM_STRATEGY
{
    STRAT_BREAKOUT = 0,  // Trobosan Breakout Martingale
    STRAT_LAYER    = 1,  // Layer / Grid Averaging
    STRAT_ZIGZAG   = 2,  // Zigzag Bouncing Martingale
    STRAT_SIGNAL   = 3   // Sinyal GT A-E + SL/TP dari level GT
};

//+------------------------------------------------------------------+
//| Input Parameters                                                 |
//+------------------------------------------------------------------+

//--- System Information
input string          _s0                  = "=========== EA PESALDO ==========="; 
sinput string         Info_System          = "EA Memburu Saldo "; 
sinput string         Info_Version         = "v1.11 [Multi-Strategy GT]"; 
sinput string         Info_Author          = "MOCHAMAD TABRANI";                  
sinput string         Info_Support         = "cindo.pages.dev";   

//--- Dashboard Layout
input string          _s1                  = "======== DASHBOARD GEOMETRY ========";
input int             X_Offset             = 20;       // Horizontal Offset (Pixels)
input int             Y_Offset             = 40;       // Vertical Offset (Pixels)
input int             Panel_Width          = 600;      // Total Dashboard Width

//--- Trading Engine Settings
input string          _s2                  = "======== GRAFIK TABRANIJ ALGO STRATEGY ========";
input ENUM_STRATEGY   InpStrategy          = STRAT_BREAKOUT; // Pilih Strategi Memburu Saldo
input ENUM_TIMEFRAMES InpGTTimeframe       = PERIOD_H1;     // GT Besar Timeframe (Signal Basis)
input double          InpLot               = 0.01;          // Base Lot Volume
input double          InpMultiplier        = 2.0;           // Martingale / Layer Volume Multiplier
input int             InpMaxSteps          = 5;             // Max Martingale / Layer Steps
input int             InpTP                = 300;           // Take Profit Distance (Points) — fallback
input int             InpSL                = 150;           // Stop Loss Distance (Points) — fallback
input int             InpLayerStepPts      = 100;           // Jarak antar layer (points)
input int             InpZigzagBouncePts   = 50;            // Toleransi bounce Zigzag (points)
input bool            InpUseGTSLTP         = true;          // Pakai level GT untuk SL/TP
input bool            InpRequireSignal     = false;         // Hanya entry jika sinyal A-E aktif
input int             InpMagic             = 888999;        // Algorithm Serial ID

//--- [v1.11] Keamanan & Optimasi
input string          _s3                  = "======== KEAMANAN & OPTIMASI (v1.11) ========";
input int             InpMaxSpreadPts      = 40;            // Max Spread (pts) utk entry baru (0=off)
input double          InpMaxEquityDDPct    = 25.0;          // Stop entry jika DD Equity > % (0=off)
input double          InpMaxDailyLossPct   = 10.0;          // Stop entry jika Loss Harian > % (0=off)
input double          InpMaxLotCap         = 5.0;           // Batas Lot Maksimum per posisi
input int             InpMinSecBetweenTrades = 5;           // Cooldown antar entry (detik, 0=off)
input bool            InpOncePerBar        = true;          // Maks 1 entry baru per bar
input bool            InpStopOnMaxStep     = true;          // Hentikan entry saat step maksimal

//--- [v1.11] Kalibrasi Sinyal GT A-E
input string          _s4                  = "======== KALIBRASI SINYAL GT A-E (v1.11) ========";
input bool            InpUseATRScale       = true;          // Skala threshold dgn ATR simbol
input int             InpATRPeriod         = 14;            // Periode ATR
input double          InpATRFactor         = 1.0;           // Faktor ATR (1.0 = 1x ATR)
input int             InpSigMomPts         = 8;             // Sinyal A: neto minimal (pts)
input int             InpSigPullbackPts    = 15;            // Sinyal B: jarak wick (pts)
input int             InpSigRangePts       = 28;            // Sinyal C: julat range maks (pts)
input int             InpSigBasePts        = 10;            // Sinyal Dasar: neto minimal (pts)

//--- Theme & Color Settings
input string          _s5                  = "======== UI THEME & PALETTE ========";
input ENUM_THEME      InpTheme             = THEME_ONYX_GOLD;   // Active Visual Theme
input color           Label_Color          = clrGold;           // Primary Label Color
input color           Value_Color          = clrWhite;          // Numerical Value Color
input color           Live_Color           = C'255,225,100';    // Real-time Accent Color

//--- Chart Visualization
input string          _s6                  = "======== CHART VISUALIZATION ========";
input bool            InpShowGTChart       = true;              // Plot GT Mathematical Levels
input int             InpLevelWidth        = 1;                 // Level Line Thickness
input ENUM_LINE_STYLE InpLevelStyle        = STYLE_SOLID;       // Level Line Pattern
input bool            InpShowLabels        = true;              // Display Level Descriptions

//+------------------------------------------------------------------+
//| [2] Global Variables                                             |
//+------------------------------------------------------------------+
double   myPoint;
int      myDigits;
datetime lastBarTime = 0;
CTrade   trade;

// Sequential State Machine
bool     g_isFirstTrade = true; // Flag untuk perdagangan pertama

// Multi-strategy state (shared with WriteGenesisJSON & trading logic)
int                g_martingaleStep  = 0;
ENUM_POSITION_TYPE g_lastDirection   = (ENUM_POSITION_TYPE)-1;
string             g_lastSignalType  = "NETRAL";
int                g_lastSignalScore = 0;
string             g_activeStrategy  = "BREAKOUT";

// [v1.11] Pengaman & throttle
datetime           g_lastEntryTime   = 0;     // Cooldown antar entry
datetime           g_lastEntryBar    = 0;     // Bar terakhir entry (once per bar)
double             g_peakEquity      = 0;     // Equity puncak sejak EA start
int                g_dayKey          = 0;     // Kunci hari server (YYYYMMDD)
double             g_dayStartEquity  = 0;
double             g_dayPeakEquity   = 0;
uint               g_lastJsonMs      = 0;     // Throttle JSON (ms)
uint               g_lastGuiMs       = 0;     // Throttle GUI (ms)
uint               g_lastLevelsMs    = 0;     // Throttle level (ms)
int                g_atrHandle       = INVALID_HANDLE; // Handle ATR utk kalibrasi sinyal

#define PREFIX          "GRAFIK TABRANIJ"
#define COLOR_BG        C'45,45,45'    // Charcoal Grey (matching the image)
#define COLOR_STRIPE    C'35,35,35'    // Darker Grey for stripes/alternating rows
#define COLOR_HDR_BG    C'65,65,65'    // Lighter Slate Grey for headers (matching the image)
#define COLOR_SUCCESS   C'0,255,140'   // Emerald
#define COLOR_DANGER    C'255,80,90'   // Ruby
#define COLOR_SILVER    C'180,180,180' // Muted Silver
#define COLOR_BORDER    C'85,85,85'    // Silver/Grey for borders

#define ROW_H           30
#define FONT_MAIN       "Segoe UI"
#define FONT_SIZE       10
#define COLOR_COUNTDOWN C'255,200,50'   // Amber Gold (Countdown)
#define VIS_PREFIX      "GT_VIS_"

// Global State for UI Tabs
enum ENUM_TABS {
    TAB_DASHBOARD,
    TAB_ABOUT,
    TAB_TRADING,
    TAB_COLORS,
    TAB_VISUAL
};
ENUM_TABS currTab = TAB_DASHBOARD;

// Global Color Theme Variables
color gClrBg, gClrHdr, gClrStripe, gClrLabel, gClrValue, gClrAccent, gClrSuccess, gClrDanger, gClrBorder;

// Runtime Modifiable Settings (Mirrored from Inputs)
ENUM_THEME   extTheme;
bool         extShowGTChart;

// Wall-clock synchronization
long         serverLocalOffset = 0;

void ApplyTheme()
{
   switch(extTheme)
   {
      case THEME_NEON_BLUE:
         gClrBg      = C'5,15,25';
         gClrHdr     = C'20,40,60';
         gClrStripe  = C'10,25,45';
         gClrLabel   = clrCyan;
         gClrValue   = clrWhite;
         gClrAccent  = clrDeepSkyBlue;
         gClrSuccess = clrSpringGreen;
         gClrDanger  = clrDeepPink;
         gClrBorder  = C'20,50,80';
         break;
      case THEME_MATRIX:
         gClrBg      = C'0,10,0';
         gClrHdr     = C'0,30,0';
         gClrStripe  = C'5,20,5';
         gClrLabel   = clrLimeGreen;
         gClrValue   = clrLime;
         gClrAccent  = clrGreen;
         gClrSuccess = clrWhite;
         gClrDanger  = clrRed;
         gClrBorder  = C'0,40,0';
         break;
      case THEME_PURE_DARK:
         gClrBg      = C'15,15,15';
         gClrHdr     = C'25,25,25';
         gClrStripe  = C'20,20,20';
         gClrLabel   = clrLightGray;
         gClrValue   = clrWhite;
         gClrAccent  = clrGray;
         gClrSuccess = clrAliceBlue;
         gClrDanger  = clrIndianRed;
         gClrBorder  = C'35,35,35';
         break;
      case THEME_ONYX_GOLD:
      default:
         gClrBg      = COLOR_BG;
         gClrHdr     = COLOR_HDR_BG;
         gClrStripe  = COLOR_STRIPE;
         gClrLabel   = Label_Color;
         gClrValue   = Value_Color;
         gClrAccent  = clrGold;
         gClrSuccess = COLOR_SUCCESS;
         gClrDanger  = COLOR_DANGER;
         gClrBorder  = COLOR_BORDER;
         break;
   }
}

//+------------------------------------------------------------------+
//| [3] Expert initialization function                               |
//+------------------------------------------------------------------+
int OnInit()
{
   myPoint  = _Point;
   myDigits = _Digits;
   
   string themeGV = PREFIX + "_" + _Symbol + "_" + IntegerToString(InpMagic) + "_THEME";
   if(GlobalVariableCheck(themeGV))
      extTheme = (ENUM_THEME)GlobalVariableGet(themeGV);
   else
      extTheme = InpTheme;
      
   string showChartGV = PREFIX + "_" + _Symbol + "_" + IntegerToString(InpMagic) + "_SHOWCHART";
   if(GlobalVariableCheck(showChartGV))
      extShowGTChart = (bool)GlobalVariableGet(showChartGV);
   else
      extShowGTChart = InpShowGTChart;
   
   serverLocalOffset = (long)TimeCurrent() - (long)TimeLocal();

   ApplyTheme();
   DeleteAllObjects();

   if(!CreateDashboard())
   {
      Print("Gagal membuat Quad-Bar Dashboard.");
      return(INIT_FAILED);
   }

   trade.SetExpertMagicNumber(InpMagic);
   EventSetTimer(1);
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason) 
{ 
   EventKillTimer(); 
   DeleteAllObjects(); 
   DeleteVisualization(); 
   if(g_atrHandle != INVALID_HANDLE)
   {
      IndicatorRelease(g_atrHandle);
      g_atrHandle = INVALID_HANDLE;
   }
   
   if(reason == REASON_REMOVE || reason == REASON_CLOSE)
   {
      string themeGV = PREFIX + "_" + _Symbol + "_" + IntegerToString(InpMagic) + "_THEME";
      string showChartGV = PREFIX + "_" + _Symbol + "_" + IntegerToString(InpMagic) + "_SHOWCHART";
      GlobalVariableDel(themeGV);
      GlobalVariableDel(showChartGV);
   }
}

void OnTick()                    
{ 
   uint nowMs = GetTickCount();
   
   // GUI update (throttle ~100 ms agar ringan di simbol cepat)
   if(nowMs - g_lastGuiMs >= 100)
   {
      UpdateGUILabels(); 
      g_lastGuiMs = nowMs;
   }
   
   UpdateSafetyTrackers();       // update equity puncak & loss harian
   ExecuteTradingLogic();        // entry baru di-filter oleh IsTradingAllowed()
   
   // Level visualization (throttle ~1 dtk)
   if(extShowGTChart && nowMs - g_lastLevelsMs >= 1000)
   {
      DrawGTLevels(); 
      g_lastLevelsMs = nowMs;
   }
   
   // JSON ke TanyaHargaBot (throttle ~1 dtk, hindari I/O tiap tick)
   if(nowMs - g_lastJsonMs >= 1000)
   {
      WriteGenesisJSON(); 
      g_lastJsonMs = nowMs;
   }
}

void OnTimer() { UpdateCountdown(); }

void OnChartEvent(const int id, const long& lparam, const double& dparam, const string& sparam)
{
   if(id == CHARTEVENT_OBJECT_CLICK)
   {
      if(sparam == PREFIX + "TAB_DB") { currTab = TAB_DASHBOARD; ResetDashboard(); }
      else if(sparam == PREFIX + "TAB_AB") { currTab = TAB_ABOUT;     ResetDashboard(); }
      else if(sparam == PREFIX + "TAB_TR") { currTab = TAB_TRADING;   ResetDashboard(); }
      else if(sparam == PREFIX + "TAB_CL") { currTab = TAB_COLORS;    ResetDashboard(); }
      else if(sparam == PREFIX + "TAB_VS") { currTab = TAB_VISUAL;    ResetDashboard(); }
      else if(sparam == PREFIX + "THM_ONYX")  
      { 
         extTheme = THEME_ONYX_GOLD; 
         GlobalVariableSet(PREFIX + "_" + _Symbol + "_" + IntegerToString(InpMagic) + "_THEME", extTheme);
         ApplyTheme(); ResetDashboard(); 
      }
      else if(sparam == PREFIX + "THM_NEON")  
      { 
         extTheme = THEME_NEON_BLUE; 
         GlobalVariableSet(PREFIX + "_" + _Symbol + "_" + IntegerToString(InpMagic) + "_THEME", extTheme);
         ApplyTheme(); ResetDashboard(); 
      }
      else if(sparam == PREFIX + "THM_MATRIX") 
      { 
         extTheme = THEME_MATRIX;    
         GlobalVariableSet(PREFIX + "_" + _Symbol + "_" + IntegerToString(InpMagic) + "_THEME", extTheme);
         ApplyTheme(); ResetDashboard(); 
      }
      else if(sparam == PREFIX + "THM_DARK")   
      { 
         extTheme = THEME_PURE_DARK;  
         GlobalVariableSet(PREFIX + "_" + _Symbol + "_" + IntegerToString(InpMagic) + "_THEME", extTheme);
         ApplyTheme(); ResetDashboard(); 
      }
      else if(sparam == PREFIX + "TOG_CHART") 
      { 
         extShowGTChart = !extShowGTChart; 
         GlobalVariableSet(PREFIX + "_" + _Symbol + "_" + IntegerToString(InpMagic) + "_SHOWCHART", extShowGTChart);
         if(!extShowGTChart) DeleteVisualization(); 
         ResetDashboard(); 
      }
      else if(sparam == PREFIX + "BTN_CLOSEALL")  // [v1.11] Tombol darurat
      { 
         CloseMyPositions(); 
      }
   }
}

//+------------------------------------------------------------------+
//| [v1.11] Fungsi Keamanan                                          |
//+------------------------------------------------------------------+

// Update tracker equity puncak & loss harian (panggil tiap tick)
void UpdateSafetyTrackers()
{
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(equity > g_peakEquity) g_peakEquity = equity;

   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   int key = dt.year * 10000 + dt.mon * 100 + dt.day;
   if(key != g_dayKey)
   {
      g_dayKey          = key;
      g_dayStartEquity  = equity;
      g_dayPeakEquity   = equity;
   }
   else if(equity > g_dayPeakEquity)
      g_dayPeakEquity = equity;
}

double GetEquityDDPct()
{
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(g_peakEquity > 0) return (g_peakEquity - eq) / g_peakEquity * 100.0;
   return 0;
}

// Gerbang keamanan utama — SEMUA entry baru harus lolos fungsi ini
bool IsTradingAllowed()
{
   // 1) Spread filter (hindari entry saat news/spread melebar)
   if(InpMaxSpreadPts > 0)
   {
      long spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
      if(spread > InpMaxSpreadPts) return false;
   }
   // 2) Cooldown antar entry
   if(InpMinSecBetweenTrades > 0 && TimeCurrent() - g_lastEntryTime < InpMinSecBetweenTrades)
      return false;
   // 3) Maks 1 entry baru per bar (cegah re-entry berulang breakout)
   if(InpOncePerBar && g_lastEntryBar == iTime(_Symbol, PERIOD_CURRENT, 0))
      return false;
   // 4) Martingale dihentikan saat mencapai max step (sampai profit)
   if(InpStopOnMaxStep && g_martingaleStep >= InpMaxSteps)
      return false;
   // 5) Drawdown equity dari puncak
   if(InpMaxEquityDDPct > 0 && g_peakEquity > 0)
   {
      double dd = (g_peakEquity - AccountInfoDouble(ACCOUNT_EQUITY)) / g_peakEquity * 100.0;
      if(dd >= InpMaxEquityDDPct) return false;
   }
   // 6) Loss harian
   if(InpMaxDailyLossPct > 0 && g_dayPeakEquity > 0)
   {
      double dd = (g_dayPeakEquity - AccountInfoDouble(ACCOUNT_EQUITY)) / g_dayPeakEquity * 100.0;
      if(dd >= InpMaxDailyLossPct) return false;
   }
   return true;
}

// Tandai bahwa entry berhasil dilakukan (cooldown + once per bar)
void MarkEntryUsed()
{
   g_lastEntryTime = TimeCurrent();
   g_lastEntryBar  = iTime(_Symbol, PERIOD_CURRENT, 0);
}

//+------------------------------------------------------------------+
//| [6] GUI Functions                                                |
//+------------------------------------------------------------------+
void DeleteAllObjects()
{
   for(int i = ObjectsTotal(0) - 1; i >= 0; i--)
   {
      string name = ObjectName(0, i);
      if(StringFind(name, PREFIX) == 0) ObjectDelete(0, name);
   }
}

void DeleteVisualization()
{
   for(int i = ObjectsTotal(0) - 1; i >= 0; i--)
   {
      string name = ObjectName(0, i);
      if(StringFind(name, VIS_PREFIX) == 0) ObjectDelete(0, name);
   }
}

void DrawGTLevels()
{
   double open  = iOpen(_Symbol, PERIOD_CURRENT, 0);
   double close = iClose(_Symbol, PERIOD_CURRENT, 0);
   double high  = iHigh(_Symbol, PERIOD_CURRENT, 0);
   double low   = iLow(_Symbol, PERIOD_CURRENT, 0);
   
   if(open == 0) return;

   double bH = MathMax(open, close), bL = MathMin(open, close);
   
   DrawHLine(VIS_PREFIX + "Tinggi", high,  gClrAccent, STYLE_DOT);
   DrawHLine(VIS_PREFIX + "Rendah", low,   gClrAccent, STYLE_DOT);
   DrawHLine(VIS_PREFIX + "Atas",   bH,    gClrLabel,  STYLE_SOLID);
   DrawHLine(VIS_PREFIX + "Bawah",  bL,    gClrLabel,  STYLE_SOLID);
   DrawHLine(VIS_PREFIX + "Awal",   open,  clrSilver,  STYLE_DASH);
   DrawHLine(VIS_PREFIX + "Inti",   close, gClrValue,  STYLE_SOLID, 2);
}

// [v1.11] Disederhanakan — style dipakai apa adanya
void DrawHLine(string name, double price, color clr, ENUM_LINE_STYLE style, int width = 1)
{
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_HLINE, 0, 0, price);
   else
      ObjectSetDouble(0, name, OBJPROP_PRICE, price);
      
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_STYLE, style);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, (width == 1) ? InpLevelWidth : width);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   if(InpShowLabels)
      ObjectSetString(0, name, OBJPROP_TEXT, " " + StringSubstr(name, StringLen(VIS_PREFIX)));
   else
      ObjectSetString(0, name, OBJPROP_TEXT, "");
}

bool CreateRect(string name, int x, int y, int w, int h, color bg, color border = clrNONE)
{
   if(!ObjectCreate(0, name, OBJ_RECTANGLE_LABEL, 0, 0, 0)) return false;
   ObjectSetInteger(0, name, OBJPROP_CORNER,      CORNER_LEFT_UPPER);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE,   x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE,   y);
   ObjectSetInteger(0, name, OBJPROP_XSIZE,       w);
   ObjectSetInteger(0, name, OBJPROP_YSIZE,       h);
   ObjectSetInteger(0, name, OBJPROP_BGCOLOR,     bg);
   ObjectSetInteger(0, name, OBJPROP_BORDER_TYPE, BORDER_FLAT);
   if(border != clrNONE) ObjectSetInteger(0, name, OBJPROP_BORDER_COLOR, border);
   ObjectSetInteger(0, name, OBJPROP_BACK,        false);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE,  false);
   return true;
}

bool CreateLabel(string name, int x, int y, string text, color clr, int size = FONT_SIZE, string font = FONT_MAIN, ENUM_ANCHOR_POINT anchor = ANCHOR_LEFT_UPPER)
{
   if(!ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0)) return false;
   ObjectSetInteger(0, name, OBJPROP_CORNER,    CORNER_LEFT_UPPER);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetString(0, name, OBJPROP_TEXT,       text);
   ObjectSetInteger(0, name, OBJPROP_COLOR,     clr);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE,  size);
   ObjectSetString(0, name, OBJPROP_FONT,       font);
   ObjectSetInteger(0, name, OBJPROP_ANCHOR,    anchor);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   return true;
}

void CreateQuadBarRow(string prefix, int y, string label)
{
   int midY      = y + ROW_H / 2;
   int dataStart = 90;
   int colW      = (Panel_Width - dataStart) / 4;
   
   CreateLabel(prefix + "_lbl", X_Offset + 20, midY, label, gClrLabel, 9, FONT_MAIN, ANCHOR_LEFT);
   CreateLabel(prefix + "_v3", X_Offset + dataStart + (int)(colW * 0.5), midY, "-", gClrValue,  9, FONT_MAIN, ANCHOR_CENTER);
   CreateLabel(prefix + "_v2", X_Offset + dataStart + (int)(colW * 1.5), midY, "-", gClrValue,  9, FONT_MAIN, ANCHOR_CENTER);
   CreateLabel(prefix + "_v1", X_Offset + dataStart + (int)(colW * 2.5), midY, "-", gClrValue,  9, FONT_MAIN, ANCHOR_CENTER);
   CreateLabel(prefix + "_v0", X_Offset + dataStart + (int)(colW * 3.5), midY, "-", gClrAccent, 9, FONT_MAIN, ANCHOR_CENTER);
}

void ResetDashboard() { DeleteAllObjects(); CreateDashboard(); }

bool CreateDashboard()
{
   int y = Y_Offset;
   int totalH = (currTab == TAB_DASHBOARD) ? 525 : 410;

   CreateRect(PREFIX + "Main", X_Offset, y, Panel_Width, totalH, gClrBg, gClrBorder);
   CreateCornerBrackets(X_Offset - 2, y - 2, Panel_Width + 4, totalH + 4, 15, gClrAccent);
   
   int tabW = (Panel_Width - 20) / 5;
   int tabX = X_Offset + 10;
   int tabY = y + 10;
   
   CreateTabButton(PREFIX + "TAB_DB", tabX + (tabW/2),          tabY, tabW, 25, "DASHBOARD", currTab == TAB_DASHBOARD);
   CreateTabButton(PREFIX + "TAB_AB", tabX + (tabW + tabW/2),   tabY, tabW, 25, "ABOUT",     currTab == TAB_ABOUT);
   CreateTabButton(PREFIX + "TAB_TR", tabX + (tabW*2 + tabW/2), tabY, tabW, 25, "TRADING",   currTab == TAB_TRADING);
   CreateTabButton(PREFIX + "TAB_CL", tabX + (tabW*3 + tabW/2), tabY, tabW, 25, "COLORS",    currTab == TAB_COLORS);
   CreateTabButton(PREFIX + "TAB_VS", tabX + (tabW*4 + tabW/2), tabY, tabW, 25, "VISUAL",    currTab == TAB_VISUAL);

   y += 45;
   
   if(currTab == TAB_DASHBOARD) CreateDashboardTab(y);
   else if(currTab == TAB_ABOUT) CreateAboutTab(y);
   else if(currTab == TAB_TRADING) CreateTradingTab(y);
   else if(currTab == TAB_COLORS) CreateColorsTab(y);
   else if(currTab == TAB_VISUAL) CreateVisualTab(y);

   ChartRedraw();
   return true;
}

void CreateDashboardTab(int y)
{
   int centerX = X_Offset + (Panel_Width / 2);
   CreateRect(PREFIX + "Hdr", X_Offset + 4, y, Panel_Width - 8, 45, gClrHdr);
   CreateLabel(PREFIX + "Title", centerX, y + 22, "Genesis Riwayat Angka Faktual Informasi Keuangan", gClrAccent, 11, FONT_MAIN, ANCHOR_CENTER);
   y += 50;
   
   int dataStart = 90;
   int colW      = (Panel_Width - dataStart) / 4;
   CreateLabel(PREFIX + "C3", X_Offset + dataStart + (int)(colW * 0.5), y, "[ GT3 ]",    clrAqua,    8, FONT_MAIN, ANCHOR_UPPER);
   CreateLabel(PREFIX + "C2", X_Offset + dataStart + (int)(colW * 1.5), y, "[ GT2 ]",    clrAqua,    8, FONT_MAIN, ANCHOR_UPPER);
   CreateLabel(PREFIX + "C1", X_Offset + dataStart + (int)(colW * 2.5), y, "[ GT1 ]",    clrAqua,    8, FONT_MAIN, ANCHOR_UPPER);
   CreateLabel(PREFIX + "C0", X_Offset + dataStart + (int)(colW * 3.5), y, "[ GT LIVE ]",gClrAccent, 8, FONT_MAIN, ANCHOR_UPPER);
   CreateLabel(PREFIX + "CountdownIcon", X_Offset + dataStart + (int)(colW * 3.5) - 32, y + 24, "p", COLOR_COUNTDOWN, 9, "Webdings", ANCHOR_UPPER);
   CreateLabel(PREFIX + "Countdown",     X_Offset + dataStart + (int)(colW * 3.5) + 8,  y + 23, "00:00:00", COLOR_COUNTDOWN, 8, FONT_MAIN, ANCHOR_UPPER);
   y += 40;

   int y_start = y;
   int y_end   = y_start + 8 * ROW_H;
   
   CreateRect(PREFIX + "Grid_V_Label", X_Offset + dataStart, y_start, 1, y_end - y_start, gClrBorder);
   for(int i = 1; i <= 4; i++)
      CreateRect(PREFIX + "Grid_V_" + IntegerToString(i), X_Offset + dataStart + colW * i, y_start, 1, y_end - y_start, gClrBorder);
   
   for(int i = 0; i <= 8; i++)
      CreateRect(PREFIX + "Grid_H_" + IntegerToString(i), X_Offset + 4, y_start + i * ROW_H, Panel_Width - 8, 1, gClrBorder);

   CreateQuadBarRow(PREFIX + "R_OH",    y, "Tinggi");    y += ROW_H;
   CreateQuadBarRow(PREFIX + "R_CH",    y, "Atas");      y += ROW_H;
   CreateQuadBarRow(PREFIX + "R_CL",    y, "Bawah");     y += ROW_H;
   CreateQuadBarRow(PREFIX + "R_OL",    y, "Rendah");    y += ROW_H;
   CreateQuadBarRow(PREFIX + "R_Awal",  y, "Awal");      y += ROW_H;
   CreateQuadBarRow(PREFIX + "R_OC",    y, "Neto");      y += ROW_H;
   CreateQuadBarRow(PREFIX + "R_LH",    y, "Inti");      y += ROW_H;
   CreateQuadBarRow(PREFIX + "R_Range", y, "Julat"); y += ROW_H + 5;

   UpdateInfoSectionOnDashboard(y);
}

void UpdateInfoSectionOnDashboard(int y)
{
   CreateRect(PREFIX + "InfoBg", X_Offset + 4, y, Panel_Width - 8, 135, gClrStripe);
   int infoY = y + 10;
   
   CreateLabel(PREFIX + "Acc_Bal",    X_Offset + 20,              infoY, "Saldo:",       gClrLabel, 8);
   CreateLabel(PREFIX + "Acc_BalVal", X_Offset + 130,             infoY, "0.00",         gClrValue, 8);
   CreateLabel(PREFIX + "Acc_Eq",     X_Offset + Panel_Width/2,   infoY, "Equity:",      gClrLabel, 8);
   CreateLabel(PREFIX + "Acc_EqVal",  X_Offset + Panel_Width - 20,infoY, "0.00",         gClrValue, 8, FONT_MAIN, ANCHOR_RIGHT_UPPER);
   
   infoY += 22;
   CreateLabel(PREFIX + "Sym_Spread",    X_Offset + 20,               infoY, "Spread:",      gClrLabel, 8);
   CreateLabel(PREFIX + "Sym_SpreadVal", X_Offset + 130,              infoY, "0",            gClrValue, 8);
   CreateLabel(PREFIX + "Sym_PL",        X_Offset + Panel_Width/2,    infoY, "Symbol P/L:",  gClrLabel, 8);
   CreateLabel(PREFIX + "Sym_PLVal",     X_Offset + Panel_Width - 20, infoY, "0.00",         gClrAccent,8, FONT_MAIN, ANCHOR_RIGHT_UPPER);

   infoY += 22;
   CreateLabel(PREFIX + "Sym_BuyExp",    X_Offset + 20,               infoY, "Buy Exp:",     gClrLabel, 8);
   CreateLabel(PREFIX + "Sym_BuyExpVal", X_Offset + 130,              infoY, "0.00 Lots",    gClrValue, 8);
   CreateLabel(PREFIX + "Acc_ML",        X_Offset + Panel_Width/2,    infoY, "Margin Level:",gClrLabel, 8);
   CreateLabel(PREFIX + "Acc_MLVal",     X_Offset + Panel_Width - 20, infoY, "0.00%",        gClrValue, 8, FONT_MAIN, ANCHOR_RIGHT_UPPER);

   infoY += 22;
   CreateLabel(PREFIX + "Sym_SellExp",    X_Offset + 20,               infoY, "Sell Exp:",   gClrLabel, 8);
   CreateLabel(PREFIX + "Sym_SellExpVal", X_Offset + 130,              infoY, "0.00 Lots",   gClrValue, 8);
   CreateLabel(PREFIX + "Acc_SOEq",       X_Offset + Panel_Width/2,    infoY, "Eq to SO:",   gClrLabel, 8);
   CreateLabel(PREFIX + "Acc_SOEqVal",    X_Offset + Panel_Width - 20, infoY, "0.00",        gClrValue, 8, FONT_MAIN, ANCHOR_RIGHT_UPPER);

   infoY += 22;
   CreateLabel(PREFIX + "Sym_SOPrice",    X_Offset + 20,               infoY, "SO Price:",   gClrLabel, 8);
   CreateLabel(PREFIX + "Sym_SOPriceVal", X_Offset + 130,              infoY, "-",           gClrValue, 8);
   CreateLabel(PREFIX + "Sym_SOPts",      X_Offset + Panel_Width/2,    infoY, "Pts to SO:",  gClrLabel, 8);
   CreateLabel(PREFIX + "Sym_SOPtsVal",   X_Offset + Panel_Width - 20, infoY, "0 pts",       gClrValue, 8, FONT_MAIN, ANCHOR_RIGHT_UPPER);
}

void CreateAboutTab(int y)
{
   int contentX = X_Offset + 20;
   int contentW = Panel_Width - 40;
   CreateRect(PREFIX + "AboutBg", X_Offset + 4, y, Panel_Width - 8, 340, gClrStripe);
   
   int lineY = y + 20;
   CreateLabel(PREFIX + "Ab_Title",   contentX, lineY, "UNTUK MENJADI BAHAGIA DALAM TRADING", gClrAccent, 11);
   lineY += 30;
   CreateLabel(PREFIX + "Ab_Desc1",   contentX, lineY, "Anda harus menghilangkan dua hal:", clrWhite, 9);
   lineY += 20;
   CreateLabel(PREFIX + "Ab_Desc2",   contentX, lineY, "Ketakutan akan masa depan yang buruk dan kenangan akan masa lalu yang buruk", clrWhite, 9);
   
   lineY += 40;
   CreateLabel(PREFIX + "Ab_DevLabel",  contentX,       lineY, "Developed by:", gClrLabel, 8);
   CreateLabel(PREFIX + "Ab_DevVal",    contentX + 120, lineY, "MOCHAMAD TABRANI", gClrValue, 8);
   lineY += 20;
   CreateLabel(PREFIX + "Ab_VerLabel",  contentX,       lineY, "Version:",      gClrLabel, 8);
   CreateLabel(PREFIX + "Ab_VerVal",    contentX + 120, lineY, "1.11 Professional", gClrValue, 8);
   lineY += 20;
   CreateLabel(PREFIX + "Ab_Method",    contentX,       lineY, "Methodology:",  gClrLabel, 8);
   CreateLabel(PREFIX + "Ab_MethodVal", contentX + 120, lineY, "Grafik Tabranij (GT) Matematika Pasar", gClrValue, 8);
   
   lineY += 50;
   CreateRect(PREFIX + "Ab_Box",    contentX, lineY, contentW, 100, gClrBg, clrSilver);
   CreateLabel(PREFIX + "Ab_Status",  contentX + 10, lineY + 10, "STATUS SISTEM: OPERASIONAL",                     gClrSuccess, 9);
   CreateLabel(PREFIX + "Ab_Lince",   contentX + 10, lineY + 30, "License: BLUCHIP Agustus 2026",                clrSilver,   8);
   CreateLabel(PREFIX + "Ab_Support", contentX + 10, lineY + 70, "Support: mql5.com/getbos | t.me/jackmusk",   gClrAccent,  8);
}

void CreateTradingTab(int y)
{
   CreateRect(PREFIX + "TradBg", X_Offset + 4, y, Panel_Width - 8, 340, gClrStripe);
   int lineY    = y + 20;
   int contentX = X_Offset + 20;

   string stratLabel = "Trobosan Breakout";
   if(InpStrategy == STRAT_LAYER)  stratLabel = "Layer / Grid";
   else if(InpStrategy == STRAT_ZIGZAG) stratLabel = "Zigzag Bounce";
   else if(InpStrategy == STRAT_SIGNAL) stratLabel = "Sinyal GT A-E";
   
   CreateLabel(PREFIX + "Tr_Title", contentX, lineY, "RINGKASAN PENGATURAN ALGORITMA", gClrAccent, 10);
   lineY += 30;
   
   CreateLabel(PREFIX + "Tr_ModeL",  contentX,       lineY, "Strategi:",     gClrLabel, 9);
   CreateLabel(PREFIX + "Tr_ModeV",  contentX + 150, lineY, stratLabel,      gClrAccent, 9);
   lineY += 22;
   CreateLabel(PREFIX + "Tr_StratL", contentX,       lineY, "Durasi GT:",    gClrLabel, 9);
   CreateLabel(PREFIX + "Tr_StratV", contentX + 150, lineY, EnumToString(InpGTTimeframe), gClrValue, 9);
   lineY += 22;
   CreateLabel(PREFIX + "Tr_LotL",   contentX,       lineY, "Volume:",       gClrLabel, 9);
   CreateLabel(PREFIX + "Tr_LotV",   contentX + 150, lineY, DoubleToString(InpLot, 2), gClrValue, 9);
   lineY += 22;
   CreateLabel(PREFIX + "Tr_StepL",  contentX,       lineY, "Martingale x:", gClrLabel, 9);
   CreateLabel(PREFIX + "Tr_StepV",  contentX + 150, lineY, DoubleToString(InpMultiplier,1) + "x / Max " + IntegerToString(InpMaxSteps), gClrValue, 9);
   lineY += 22;
   CreateLabel(PREFIX + "Tr_TPL",    contentX,       lineY, "TP / SL:",      gClrLabel, 9);
   CreateLabel(PREFIX + "Tr_TPV",    contentX + 150, lineY, IntegerToString(InpTP) + " / " + IntegerToString(InpSL) + " pts", gClrValue, 9);
   lineY += 22;
   CreateLabel(PREFIX + "Tr_GTSL",   contentX,       lineY, "SL/TP dari GT:", gClrLabel, 9);
   CreateLabel(PREFIX + "Tr_GTSLV",  contentX + 150, lineY, InpUseGTSLTP ? "YA" : "TIDAK", gClrValue, 9);
   lineY += 22;
   CreateLabel(PREFIX + "Tr_SigL",   contentX,       lineY, "Sinyal terakhir:", gClrLabel, 9);
   CreateLabel(PREFIX + "Tr_SigV",   contentX + 150, lineY, g_lastSignalType + " (" + IntegerToString(g_lastSignalScore) + "/10)", gClrAccent, 9);
   
   lineY += 35;
   CreateLabel(PREFIX + "Tr_Note",  contentX, lineY, "Ubah strategi via F7 → Inputs → InpStrategy", clrSilver, 8);
   lineY += 15;
   CreateLabel(PREFIX + "Tr_Note2", contentX, lineY, "Trobosan | Layer | Zigzag | Sinyal GT (A-E)", clrSilver, 8);

   // [v1.11] Tombol darurat tutup semua posisi
   lineY += 30;
   CreateButton(PREFIX + "BTN_CLOSEALL", X_Offset + Panel_Width/2, lineY, 220, 35, "TUTUP SEMUA POSISI", clrWhite, gClrDanger);
}

void CreateColorsTab(int y)
{
   CreateRect(PREFIX + "ColBg", X_Offset + 4, y, Panel_Width - 8, 340, gClrStripe);
   int lineY   = y + 20;
   int centerX = X_Offset + Panel_Width/2;
   
   CreateLabel(PREFIX + "Cl_Title", centerX, lineY, "PILIH TAMPILAN TEMA", gClrAccent, 11, FONT_MAIN, ANCHOR_CENTER);
   lineY += 50;
   
   int btnW = 180, btnH = 35;
   CreateButton(PREFIX + "THM_ONYX",   centerX, lineY, btnW, btnH, "ONYX & GOLD",  clrWhite, C'35,35,35');
   lineY += 50;
   CreateButton(PREFIX + "THM_NEON",   centerX, lineY, btnW, btnH, "NEON BLUE",    clrWhite, C'20,40,60');
   lineY += 50;
   CreateButton(PREFIX + "THM_MATRIX", centerX, lineY, btnW, btnH, "RETRO MATRIX", clrWhite, C'10,50,10');
   
   lineY += 60;
   CreateLabel(PREFIX + "Cl_Note", centerX, lineY, "Perubahan tema yang langsung diterapkan di semua tab (halaman/lembar kerja).", clrSilver, 8, FONT_MAIN, ANCHOR_CENTER);
}

void CreateVisualTab(int y)
{
   CreateRect(PREFIX + "VisBg", X_Offset + 4, y, Panel_Width - 8, 340, gClrStripe);
   int lineY   = y + 20;
   int centerX = X_Offset + Panel_Width/2;
   
   CreateLabel(PREFIX + "Vs_Title", centerX, lineY, "PENGATURAN TAMPILAN", gClrAccent, 11, FONT_MAIN, ANCHOR_CENTER);
   lineY += 60;
   
   string toggleText = extShowGTChart ? "MENONAKTIFKAN LEVEL" : "MENGAKTIFKAN LEVEL";
   color  toggleBg   = extShowGTChart ? gClrDanger : gClrSuccess;
   
   CreateButton(PREFIX + "TOG_CHART", centerX, lineY, 220, 40, toggleText, clrWhite, toggleBg);
   
   lineY += 80;
   CreateLabel(PREFIX + "Vs_Desc",  centerX, lineY,      "Mengaktifkan/menonaktifkan tampilan garis GT secara langsung", clrWhite, 9, FONT_MAIN, ANCHOR_CENTER);
   lineY += 20;
   CreateLabel(PREFIX + "Vs_Desc2", centerX, lineY, "(Tinggi, Rendah, Awal, Inti) di grafik tabranij.", clrWhite, 9, FONT_MAIN, ANCHOR_CENTER);
}

bool CreateTabButton(string name, int x, int y, int w, int h, string text, bool active)
{
   if(!ObjectCreate(0, name, OBJ_BUTTON, 0, 0, 0)) return false;
   ObjectSetInteger(0, name, OBJPROP_CORNER,       CORNER_LEFT_UPPER);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE,    x - (w/2));
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE,    y);
   ObjectSetInteger(0, name, OBJPROP_XSIZE,        w - 4);
   ObjectSetInteger(0, name, OBJPROP_YSIZE,        h);
   ObjectSetString (0, name, OBJPROP_TEXT,         text);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE,     8);
   ObjectSetInteger(0, name, OBJPROP_COLOR,        active ? clrWhite  : clrSilver);
   ObjectSetInteger(0, name, OBJPROP_BGCOLOR,      active ? gClrAccent: gClrHdr);
   ObjectSetInteger(0, name, OBJPROP_BORDER_COLOR, active ? clrWhite  : clrDimGray);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE,   false);
   return true;
}

bool CreateButton(string name, int x, int y, int w, int h, string text, color txtClr, color bgClr)
{
   if(!ObjectCreate(0, name, OBJ_BUTTON, 0, 0, 0)) return false;
   ObjectSetInteger(0, name, OBJPROP_CORNER,       CORNER_LEFT_UPPER);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE,    x - (w/2));
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE,    y - (h/2));
   ObjectSetInteger(0, name, OBJPROP_XSIZE,        w);
   ObjectSetInteger(0, name, OBJPROP_YSIZE,        h);
   ObjectSetString (0, name, OBJPROP_TEXT,         text);
   ObjectSetInteger(0, name, OBJPROP_COLOR,        txtClr);
   ObjectSetInteger(0, name, OBJPROP_BGCOLOR,      bgClr);
   ObjectSetInteger(0, name, OBJPROP_BORDER_COLOR, clrSilver);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE,     8);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE,   false);
   return true;
}

void CreateCornerBrackets(int x, int y, int w, int h, int size, color clr)
{
   CreateRect(PREFIX+"TL1", x,          y,          size, 2,    clr); CreateRect(PREFIX+"TL2", x,          y,          2, size, clr);
   CreateRect(PREFIX+"TR1", x+w-size,   y,          size, 2,    clr); CreateRect(PREFIX+"TR2", x+w-2,      y,          2, size, clr);
   CreateRect(PREFIX+"BL1", x,          y+h-2,      size, 2,    clr); CreateRect(PREFIX+"BL2", x,          y+h-size,   2, size, clr);
   CreateRect(PREFIX+"BR1", x+w-size,   y+h-2,      size, 2,    clr); CreateRect(PREFIX+"BR2", x+w-2,      y+h-size,   2, size, clr);
}

//+------------------------------------------------------------------+
//| [7] Logic Functions                                              |
//+------------------------------------------------------------------+
void UpdateGUILabels()
{
   UpdateBarData(3, "_v3", gClrValue);
   UpdateBarData(2, "_v2", gClrValue);
   UpdateBarData(1, "_v1", gClrValue);
   UpdateBarData(0, "_v0", gClrAccent);
   
   UpdateInfoSection();
   ChartRedraw();
}

void UpdateInfoSection()
{
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity  = AccountInfoDouble(ACCOUNT_EQUITY);
   int    spread  = (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   
   double symbolPL    = 0;
   double buyLots     = 0;
   double sellLots    = 0;
   double buyPriceSum = 0;
   double sellPriceSum= 0;
   
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
      {
         if(PositionGetString(POSITION_SYMBOL) == _Symbol)
         {
            double lots  = PositionGetDouble(POSITION_VOLUME);
            double price = PositionGetDouble(POSITION_PRICE_OPEN);
            ENUM_POSITION_TYPE posType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
            
            if(posType == POSITION_TYPE_BUY)  { buyLots  += lots; buyPriceSum  += price * lots; }
            else if(posType == POSITION_TYPE_SELL) { sellLots += lots; sellPriceSum += price * lots; }
            symbolPL += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
         }
      }
   }
   
   double avgBuyPrice  = (buyLots  > 0) ? buyPriceSum  / buyLots  : 0;
   double avgSellPrice = (sellLots > 0) ? sellPriceSum / sellLots : 0;
   
   SetVal(PREFIX + "Acc_BalVal",    DoubleToString(balance, 2), gClrValue);
   SetVal(PREFIX + "Acc_EqVal",     DoubleToString(equity, 2),  gClrValue);
   SetVal(PREFIX + "Sym_SpreadVal", IntegerToString(spread),    gClrValue);

   double netLots         = buyLots - sellLots;
   double tickSize        = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue       = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double pointValuePerLot= (tickSize > 0) ? tickValue * (myPoint / tickSize) : myPoint;
   double pointValueTotal = MathAbs(netLots) * pointValuePerLot;

   double ptsFloating = 0;
   if(pointValueTotal > 0)
      ptsFloating = symbolPL / pointValueTotal;

   string plStr  = "";
   color  plColor= gClrValue;
   
   if(symbolPL > 0.005)
   {
      plColor = gClrSuccess;
      if(buyLots > 0 || sellLots > 0)
         plStr = (pointValueTotal > 0) ? StringFormat("▲ +%.2f (+%d pts)", symbolPL, (int)MathRound(ptsFloating))
                                       : StringFormat("▲ +%.2f (Terkunci)", symbolPL);
      else
         plStr = StringFormat("▲ +%.2f (0 pts)", symbolPL);
   }
   else if(symbolPL < -0.005)
   {
      plColor = gClrDanger;
      if(buyLots > 0 || sellLots > 0)
         plStr = (pointValueTotal > 0) ? StringFormat("▼ %.2f (%d pts)", symbolPL, (int)MathRound(ptsFloating))
                                       : StringFormat("▼ %.2f (Terkunci)", symbolPL);
      else
         plStr = StringFormat("▼ %.2f (0 pts)", symbolPL);
   }
   else
   {
      plColor = gClrValue;
      plStr   = "0.00 (0 pts)";
   }
   SetVal(PREFIX + "Sym_PLVal", plStr, plColor);

   double margin      = AccountInfoDouble(ACCOUNT_MARGIN);
   double marginLevel = AccountInfoDouble(ACCOUNT_MARGIN_LEVEL);
   double stopOutLevel= AccountInfoDouble(ACCOUNT_MARGIN_SO_SO);
   long   stopOutMode = AccountInfoInteger(ACCOUNT_MARGIN_SO_MODE);

   string buyExpStr       = "0.00 Lots";
   string sellExpStr      = "0.00 Lots";
   string ptsToSOStr      = "-";
   string eqToSOStr       = "-";
   string marginLevelStr  = "0.00%";
   string stopOutPriceStr = "-";
   color  riskColor       = gClrValue;

   int    dispDigits    = (myDigits > 4) ? 4 : myDigits;
   string buyPriceStr   = DoubleToString(avgBuyPrice, dispDigits);
   string sellPriceStr  = DoubleToString(avgSellPrice, dispDigits);

   if(buyLots  > 0) buyExpStr  = StringFormat("%.2f @ %s ▲", buyLots,  buyPriceStr);
   if(sellLots > 0) sellExpStr = StringFormat("%.2f @ %s ▼", sellLots, sellPriceStr);

   if(buyLots > 0 || sellLots > 0)
   {
      if(margin > 0)
      {
         marginLevelStr = StringFormat("%.1f%% (SO: %.1f%%)", marginLevel, stopOutLevel);
         
         if(marginLevel < 150.0)       riskColor = gClrDanger;
         else if(marginLevel < 300.0)  riskColor = clrOrange;

         double equitySO  = (stopOutMode == ACCOUNT_STOPOUT_MODE_PERCENT) ? (stopOutLevel * margin) / 100.0 : stopOutLevel;
         double equityToSO= equity - equitySO;
         eqToSOStr = DoubleToString(equityToSO, 2);

         if(pointValueTotal > 0)
         {
            double ptsToSO    = equityToSO / pointValueTotal;
            ptsToSOStr        = StringFormat("%d pts", (int)MathMax(0, MathRound(ptsToSO)));
            double soPrice    = (netLots > 0) ? SymbolInfoDouble(_Symbol, SYMBOL_BID) - ptsToSO * myPoint
                                              : SymbolInfoDouble(_Symbol, SYMBOL_ASK) + ptsToSO * myPoint;
            stopOutPriceStr   = DoubleToString(soPrice, dispDigits);
         }
         else
         {
            ptsToSOStr      = "Terkunci";
            stopOutPriceStr = "Terkunci";
         }
      }
   }

   SetVal(PREFIX + "Sym_BuyExpVal",  buyExpStr,       buyLots  > 0 ? gClrSuccess : gClrValue);
   SetVal(PREFIX + "Sym_SellExpVal", sellExpStr,      sellLots > 0 ? gClrDanger  : gClrValue);
   SetVal(PREFIX + "Acc_MLVal",      marginLevelStr,  riskColor);
   SetVal(PREFIX + "Acc_SOEqVal",    eqToSOStr,       riskColor);
   SetVal(PREFIX + "Sym_SOPriceVal", stopOutPriceStr, riskColor);
   SetVal(PREFIX + "Sym_SOPtsVal",   ptsToSOStr,      riskColor);
}


//+------------------------------------------------------------------+
//| Tulis data Genesis ke file JSON (dibaca oleh TanyaHargaBot)      |
//| File: MQL5/Files/genesis_data.json (atau Common\Files)           |
//+------------------------------------------------------------------+
void WriteGenesisJSON()
{
   // Hitung data GT LIVE (shift 0) — sama seperti UpdateBarData
   double open0  = iOpen (_Symbol, PERIOD_CURRENT, 0);
   double close0 = iClose(_Symbol, PERIOD_CURRENT, 0);
   double high0  = iHigh (_Symbol, PERIOD_CURRENT, 0);
   double low0   = iLow  (_Symbol, PERIOD_CURRENT, 0);
   if(open0 == 0) return;

   int    oc0 = (int)((close0 - open0) / myPoint);
   int    lh0 = (int)((high0  - low0)  / myPoint);
   double bH0 = MathMax(open0, close0);
   double bL0 = MathMin(open0, close0);
   int    ch0 = (int)((high0 - bH0) / myPoint);
   int    cl0 = (int)((bL0 - low0) / myPoint);

   // GT1, GT2, GT3 (opsional, untuk riwayat)
   double open1  = iOpen (_Symbol, PERIOD_CURRENT, 1);
   double close1 = iClose(_Symbol, PERIOD_CURRENT, 1);
   double high1  = iHigh (_Symbol, PERIOD_CURRENT, 1);
   double low1   = iLow  (_Symbol, PERIOD_CURRENT, 1);

   double open2  = iOpen (_Symbol, PERIOD_CURRENT, 2);
   double close2 = iClose(_Symbol, PERIOD_CURRENT, 2);
   double high2  = iHigh (_Symbol, PERIOD_CURRENT, 2);
   double low2   = iLow  (_Symbol, PERIOD_CURRENT, 2);

   double open3  = iOpen (_Symbol, PERIOD_CURRENT, 3);
   double close3 = iClose(_Symbol, PERIOD_CURRENT, 3);
   double high3  = iHigh (_Symbol, PERIOD_CURRENT, 3);
   double low3   = iLow  (_Symbol, PERIOD_CURRENT, 3);

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   int    spread = (int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity  = AccountInfoDouble(ACCOUNT_EQUITY);

   // --- Posisi akun (sama logika UpdateInfoSection) ---
   double symbolPL    = 0;
   double buyLots     = 0;
   double sellLots    = 0;
   double buyPriceSum = 0;
   double sellPriceSum= 0;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
      {
         if(PositionGetString(POSITION_SYMBOL) == _Symbol)
         {
            double lots  = PositionGetDouble(POSITION_VOLUME);
            double price = PositionGetDouble(POSITION_PRICE_OPEN);
            ENUM_POSITION_TYPE posType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
            if(posType == POSITION_TYPE_BUY)  { buyLots  += lots; buyPriceSum  += price * lots; }
            else if(posType == POSITION_TYPE_SELL) { sellLots += lots; sellPriceSum += price * lots; }
            symbolPL += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
         }
      }
   }

   double avgBuyPrice  = (buyLots  > 0) ? buyPriceSum  / buyLots  : 0;
   double avgSellPrice = (sellLots > 0) ? sellPriceSum / sellLots : 0;
   double netLots      = buyLots - sellLots;
   double tickSize     = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue    = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double pointValuePerLot = (tickSize > 0) ? tickValue * (myPoint / tickSize) : myPoint;
   double pointValueTotal  = MathAbs(netLots) * pointValuePerLot;
   double ptsFloating = (pointValueTotal > 0) ? symbolPL / pointValueTotal : 0;

   double margin      = AccountInfoDouble(ACCOUNT_MARGIN);
   double marginLevel = AccountInfoDouble(ACCOUNT_MARGIN_LEVEL);
   double stopOutLevel= AccountInfoDouble(ACCOUNT_MARGIN_SO_SO);
   long   stopOutMode = AccountInfoInteger(ACCOUNT_MARGIN_SO_MODE);

   string buy_exp  = "0.00 Lots";
   string sell_exp = "0.00 Lots";
   string pts_to_so = "-";
   string eq_to_so  = "-";
   string so_price  = "-";
   string ml_str    = "0.00%";
   int    dispDigits = (myDigits > 4) ? 4 : myDigits;

   if(buyLots  > 0) buy_exp  = StringFormat("%.2f @ %s", buyLots,  DoubleToString(avgBuyPrice, dispDigits));
   if(sellLots > 0) sell_exp = StringFormat("%.2f @ %s", sellLots, DoubleToString(avgSellPrice, dispDigits));

   if((buyLots > 0 || sellLots > 0) && margin > 0)
   {
      ml_str = StringFormat("%.1f%% (SO: %.1f%%)", marginLevel, stopOutLevel);
      double equitySO  = (stopOutMode == ACCOUNT_STOPOUT_MODE_PERCENT) ? (stopOutLevel * margin) / 100.0 : stopOutLevel;
      double equityToSO= equity - equitySO;
      eq_to_so = DoubleToString(equityToSO, 2);
      if(pointValueTotal > 0)
      {
         double ptsToSO = equityToSO / pointValueTotal;
         pts_to_so = StringFormat("%d pts", (int)MathMax(0, MathRound(ptsToSO)));
         double soPrice = (netLots > 0) ? bid - ptsToSO * myPoint : ask + ptsToSO * myPoint;
         so_price = DoubleToString(soPrice, dispDigits);
      }
      else
      {
         pts_to_so = "Terkunci";
         so_price  = "Terkunci";
      }
   }

   string waktu = TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS);

   // Bangun JSON manual (tanpa library)
   string json = "{";
   json += "\"symbol\":\"" + _Symbol + "\",";
   json += "\"time\":\"" + waktu + "\",";
   json += "\"bid\":" + DoubleToString(bid, myDigits) + ",";
   json += "\"ask\":" + DoubleToString(ask, myDigits) + ",";
   json += "\"price\":" + DoubleToString((bid+ask)/2.0, myDigits) + ",";
   json += "\"spread\":" + IntegerToString(spread) + ",";

   // === GT LIVE (utama) ===
   json += "\"open\":"  + DoubleToString(open0,  myDigits) + ",";
   json += "\"high\":"  + DoubleToString(high0,  myDigits) + ",";
   json += "\"low\":"   + DoubleToString(low0,   myDigits) + ",";
   json += "\"close\":" + DoubleToString(close0, myDigits) + ",";
   json += "\"awal\":"  + DoubleToString(open0,  myDigits) + ",";
   json += "\"tinggi\":"+ DoubleToString(high0,  myDigits) + ",";
   json += "\"bawah\":" + DoubleToString(low0,   myDigits) + ",";
   json += "\"atas\":"  + DoubleToString(bH0,    myDigits) + ",";
   json += "\"badan_bawah\":" + DoubleToString(bL0, myDigits) + ",";
   json += "\"neto\":"  + IntegerToString(oc0) + ",";
   json += "\"inti\":"  + DoubleToString(close0, myDigits) + ",";
   json += "\"julat\":" + IntegerToString(lh0) + ",";
   json += "\"ch\":" + IntegerToString(ch0) + ",";
   json += "\"cl\":" + IntegerToString(cl0) + ",";

   // === Riwayat GT1 GT2 GT3 ===
   json += "\"gt1\":{";
   json += "\"open\":" + DoubleToString(open1,myDigits) + ",\"high\":" + DoubleToString(high1,myDigits);
   json += ",\"low\":" + DoubleToString(low1,myDigits) + ",\"close\":" + DoubleToString(close1,myDigits);
   json += ",\"neto\":" + IntegerToString((int)((close1-open1)/myPoint));
   json += ",\"julat\":" + IntegerToString((int)((high1-low1)/myPoint)) + "},";

   json += "\"gt2\":{";
   json += "\"open\":" + DoubleToString(open2,myDigits) + ",\"high\":" + DoubleToString(high2,myDigits);
   json += ",\"low\":" + DoubleToString(low2,myDigits) + ",\"close\":" + DoubleToString(close2,myDigits);
   json += ",\"neto\":" + IntegerToString((int)((close2-open2)/myPoint));
   json += ",\"julat\":" + IntegerToString((int)((high2-low2)/myPoint)) + "},";

   json += "\"gt3\":{";
   json += "\"open\":" + DoubleToString(open3,myDigits) + ",\"high\":" + DoubleToString(high3,myDigits);
   json += ",\"low\":" + DoubleToString(low3,myDigits) + ",\"close\":" + DoubleToString(close3,myDigits);
   json += ",\"neto\":" + IntegerToString((int)((close3-open3)/myPoint));
   json += ",\"julat\":" + IntegerToString((int)((high3-low3)/myPoint)) + "},";

   // === Akun & posisi ===
   json += "\"balance\":" + DoubleToString(balance, 2) + ",";
   json += "\"equity\":"  + DoubleToString(equity, 2) + ",";
   json += "\"buy_lots\":" + DoubleToString(buyLots, 2) + ",";
   json += "\"sell_lots\":" + DoubleToString(sellLots, 2) + ",";
   json += "\"avg_buy\":" + DoubleToString(avgBuyPrice, dispDigits) + ",";
   json += "\"avg_sell\":" + DoubleToString(avgSellPrice, dispDigits) + ",";
   json += "\"buy_exp\":\"" + buy_exp + "\",";
   json += "\"sell_exp\":\"" + sell_exp + "\",";
   json += "\"symbol_pl\":" + DoubleToString(symbolPL, 2) + ",";
   json += "\"symbol_pl_pts\":" + IntegerToString((int)MathRound(ptsFloating)) + ",";
   json += "\"margin\":" + DoubleToString(margin, 2) + ",";
   json += "\"margin_level\":" + DoubleToString(marginLevel, 1) + ",";
   json += "\"margin_level_str\":\"" + ml_str + "\",";
   json += "\"so_level\":" + DoubleToString(stopOutLevel, 1) + ",";
   json += "\"so_price\":\"" + so_price + "\",";
   json += "\"eq_to_so\":\"" + eq_to_so + "\",";
   json += "\"pts_to_so\":\"" + pts_to_so + "\",";
   json += "\"timeframe\":\"" + EnumToString(Period()) + "\",";
   // === Strategi & Sinyal EA ===
   string stratName = "BREAKOUT";
   if(InpStrategy == STRAT_LAYER)  stratName = "LAYER";
   else if(InpStrategy == STRAT_ZIGZAG) stratName = "ZIGZAG";
   else if(InpStrategy == STRAT_SIGNAL) stratName = "SIGNAL";
   json += "\"strategy\":\"" + stratName + "\",";
   json += "\"signal_type\":\"" + g_lastSignalType + "\",";
   json += "\"signal_score\":" + IntegerToString(g_lastSignalScore) + ",";
   json += "\"martingale_step\":" + IntegerToString(g_martingaleStep) + ",";
   json += "\"positions\":" + IntegerToString(CountMyPositions()) + ",";
   // [v1.11] Status pengaman utk TanyaHargaBot
   json += "\"trading_allowed\":" + (IsTradingAllowed() ? "true" : "false") + ",";
   json += "\"equity_dd_pct\":" + DoubleToString(GetEquityDDPct(), 2);
   json += "}";

   // Tulis ke MQL5/Files/genesis_data.json (folder terminal)
   // FILE_COMMON = bisa dibaca dari luar lebih mudah (Common\Files)
   int h = FileOpen("genesis_data.json", FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON);
   if(h == INVALID_HANDLE)
   {
      // Fallback tanpa FILE_COMMON
      h = FileOpen("genesis_data.json", FILE_WRITE|FILE_TXT|FILE_ANSI);
   }
   if(h != INVALID_HANDLE)
   {
      FileWriteString(h, json);
      FileClose(h);
   }
}


void UpdateBarData(int shift, string suffix, color baseClr)
{
   double open  = iOpen (_Symbol, PERIOD_CURRENT, shift);
   double close = iClose(_Symbol, PERIOD_CURRENT, shift);
   double high  = iHigh (_Symbol, PERIOD_CURRENT, shift);
   double low   = iLow  (_Symbol, PERIOD_CURRENT, shift);
   
   if(open == 0) return;

   int    oc = (int)((close - open) / myPoint);
   int    lh = (int)((high  - low)  / myPoint);
   double bH = MathMax(open, close), bL = MathMin(open, close);
   int    ch = (int)((high - bH) / myPoint), cl = (int)((bL - low) / myPoint);

   SetVal(PREFIX + "R_OH"    + suffix, DoubleToString(high,  myDigits), baseClr);
   SetVal(PREFIX + "R_CH"    + suffix, StringFormat("%d", ch),          baseClr);
   SetVal(PREFIX + "R_CL"    + suffix, StringFormat("%d", cl),          baseClr);
   SetVal(PREFIX + "R_OL"    + suffix, DoubleToString(low,   myDigits), baseClr);
   SetVal(PREFIX + "R_Awal"  + suffix, DoubleToString(open,  myDigits), baseClr);
   string ocStr = oc >= 0 ? StringFormat("%d ▲", oc) : StringFormat("%d ▼", -oc);
   SetVal(PREFIX + "R_OC"    + suffix, ocStr, oc >= 0 ? gClrSuccess : gClrDanger);
   SetVal(PREFIX + "R_LH"    + suffix, DoubleToString(close, myDigits), baseClr);
   SetVal(PREFIX + "R_Range" + suffix, StringFormat("%d", lh),          baseClr);
}

void SetVal(string name, string txt, color clr)
{
   ObjectSetString (0, name, OBJPROP_TEXT,  txt);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
}

//+------------------------------------------------------------------+
//| [8] Countdown Timer - Hitung Mundur GT Live                      |
//+------------------------------------------------------------------+
void UpdateCountdown()
{
   ENUM_TIMEFRAMES tf            = Period();
   int             periodSeconds = PeriodSeconds(tf);
   datetime        serverTimeLive= (datetime)((long)TimeLocal() + serverLocalOffset);
   datetime        barOpenTime   = iTime(_Symbol, tf, 0);
   int             elapsed       = (int)(serverTimeLive - barOpenTime);
   int             remaining     = periodSeconds - elapsed;
   
   if(remaining < 0) remaining = 0;
   
   int hours   = remaining / 3600;
   int minutes = (remaining % 3600) / 60;
   int seconds = remaining % 60;
   
   string countdownText = (hours > 0) ? StringFormat("%02d:%02d:%02d", hours, minutes, seconds)
                                      : StringFormat("%02d:%02d", minutes, seconds);
   
   color cdColor;
   if(remaining <= 10)
      cdColor = clrRed;
   else if(remaining <= 60)
   {
      color rainbow[] = {clrCyan, clrMagenta, clrYellow, clrLime, clrOrange, clrWhite, clrRed, clrBlue, clrGreen, clrAqua};
      cdColor = rainbow[seconds % ArraySize(rainbow)];
   }
   else
      cdColor = COLOR_COUNTDOWN;
   
   SetVal(PREFIX + "CountdownIcon", "p",             cdColor);
   SetVal(PREFIX + "Countdown",     countdownText,   cdColor);
   ChartRedraw();
}

//+------------------------------------------------------------------+
//| [9] EA Trading Logic - Multi Strategy GT                         |
//|  STRAT_BREAKOUT : Trobosan + Instant Reverse Martingale          |
//|  STRAT_LAYER    : Layer / Grid averaging                         |
//|  STRAT_ZIGZAG   : Zigzag Bouncing Martingale                     |
//|  STRAT_SIGNAL   : Sinyal GT A-E + SL/TP dari level GT            |
//+------------------------------------------------------------------+

//--- Helpers
int CountMyPositions()
{
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
         if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
            PositionGetInteger(POSITION_MAGIC) == (long)InpMagic)
            count++;
   }
   return count;
}

double NormalizeLot(double lot)
{
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double stepLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(stepLot <= 0) stepLot = 0.01;
   lot = MathMax(lot, minLot);
   lot = MathMin(lot, maxLot);
   lot = NormalizeDouble(MathRound(lot / stepLot) * stepLot, 2);
   return lot;
}

// [v1.11] Lot dibatasi oleh InpMaxLotCap
double CalcNextLot()
{
   double nextLot = InpLot;
   if(g_martingaleStep > 0)
      nextLot = InpLot * MathPow(InpMultiplier, g_martingaleStep);
   nextLot = NormalizeLot(nextLot);
   if(nextLot > InpMaxLotCap) nextLot = NormalizeLot(InpMaxLotCap);
   return nextLot;
}

int GetGT_RangePoints(int shift = 1)
{
   double high = iHigh(_Symbol, InpGTTimeframe, shift);
   double low  = iLow (_Symbol, InpGTTimeframe, shift);
   if(high == 0 || low == 0) return 0;
   return (int)((high - low) / myPoint);
}

//--- Hitung SL/TP dari level GT atau fallback points
// [v1.11] + validasi jarak minimal SL/TP sesuai aturan broker
void CalcGTSLTP(ENUM_POSITION_TYPE type, double entry, double &sl, double &tp)
{
   double prevHigh = iHigh(_Symbol, InpGTTimeframe, 1);
   double prevLow  = iLow (_Symbol, InpGTTimeframe, 1);
   double liveHigh = iHigh(_Symbol, PERIOD_CURRENT, 0);
   double liveLow  = iLow (_Symbol, PERIOD_CURRENT, 0);
   int    rangePts = GetGT_RangePoints(1);
   if(rangePts <= 0) rangePts = InpTP;

   if(InpUseGTSLTP && prevHigh > 0 && prevLow > 0)
   {
      if(type == POSITION_TYPE_BUY)
      {
         sl = NormalizeDouble(MathMin(prevLow, liveLow) - 5 * myPoint, myDigits);
         tp = NormalizeDouble(entry + MathMax(rangePts, InpTP) * myPoint, myDigits);
      }
      else
      {
         sl = NormalizeDouble(MathMax(prevHigh, liveHigh) + 5 * myPoint, myDigits);
         tp = NormalizeDouble(entry - MathMax(rangePts, InpTP) * myPoint, myDigits);
      }
   }
   else
   {
      if(type == POSITION_TYPE_BUY)
      {
         sl = NormalizeDouble(entry - InpSL * myPoint, myDigits);
         tp = NormalizeDouble(entry + InpTP * myPoint, myDigits);
      }
      else
      {
         sl = NormalizeDouble(entry + InpSL * myPoint, myDigits);
         tp = NormalizeDouble(entry - InpTP * myPoint, myDigits);
      }
   }

   // Pastikan jarak SL/TP >= stops level broker (cek SYMBOL_TRADE_STOPS_LEVEL)
   long stopsLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   if(stopsLevel > 0)
   {
      double minDist = stopsLevel * myPoint;
      if(type == POSITION_TYPE_BUY)
      {
         if(sl > 0 && entry - sl < minDist) sl = entry - minDist;
         if(tp > 0 && tp - entry < minDist) tp = entry + minDist;
      }
      else
      {
         if(sl > 0 && sl - entry < minDist) sl = entry + minDist;
         if(tp > 0 && entry - tp < minDist) tp = entry - minDist;
      }
   }
   sl = NormalizeDouble(sl, myDigits);
   tp = NormalizeDouble(tp, myDigits);
}

// [v1.11] Cek margin cukup + validasi sebelum kirim order
bool OpenPosition(ENUM_POSITION_TYPE type, double lot, string comment)
{
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double price = (type == POSITION_TYPE_BUY) ? ask : bid;
   double sl = 0, tp = 0;
   CalcGTSLTP(type, price, sl, tp);

   // Cek margin cukup sebelum entry
   double marginNeed = 0;
   ENUM_ORDER_TYPE ot = (type == POSITION_TYPE_BUY) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   if(!OrderCalcMargin(ot, _Symbol, lot, price, marginNeed))
   {
      Print("GT: Gagal hitung margin untuk ", lot, " lot.");
      return false;
   }
   if(marginNeed > AccountInfoDouble(ACCOUNT_MARGIN_FREE))
   {
      Print("GT: Margin tidak cukup. Butuh ", DoubleToString(marginNeed, 2),
            " | Free: ", DoubleToString(AccountInfoDouble(ACCOUNT_MARGIN_FREE), 2));
      return false;
   }

   bool ok = false;
   if(type == POSITION_TYPE_BUY)
      ok = trade.Buy(lot, _Symbol, price, sl, tp, comment);
   else
      ok = trade.Sell(lot, _Symbol, price, sl, tp, comment);

   if(ok)
   {
      MarkEntryUsed();  // aktifkan cooldown + once per bar
      g_lastDirection = type;
      Print("GT [", g_activeStrategy, "] ", (type == POSITION_TYPE_BUY ? "BUY" : "SELL"),
            " | Lot:", DoubleToString(lot, 2),
            " | SL:", DoubleToString(sl, myDigits),
            " | TP:", DoubleToString(tp, myDigits),
            " | ", comment);
   }
   else
      Print("GT Order gagal: ", trade.ResultRetcodeDescription());
   return ok;
}

// [v1.11] Unit threshold adaptif dari ATR (kalibrasi per simbol)
int GetSignalUnitPts()
{
   int unit = InpSigBasePts;
   if(InpUseATRScale)
   {
      if(g_atrHandle == INVALID_HANDLE)
         g_atrHandle = iATR(_Symbol, InpGTTimeframe, InpATRPeriod);
      if(g_atrHandle != INVALID_HANDLE)
      {
         double buf[];
         if(CopyBuffer(g_atrHandle, 0, 0, 1, buf) == 1 && buf[0] > 0)
         {
            int atrPts = (int)(buf[0] / myPoint);
            unit = MathMax(unit, (int)(atrPts * InpATRFactor));
         }
      }
   }
   return unit;
}

//--- Engine Sinyal GT A-E (mirror bot signal_engine)
// [v1.11] Threshold dapat diskalakan otomatis dengan ATR
// Return: 1=BUY, -1=SELL, 0=NETRAL; score 0-10
int EvaluateGTSignal(int &score, string &label)
{
   score = 5;
   label = "NETRAL";

   double open0  = iOpen (_Symbol, PERIOD_CURRENT, 0);
   double close0 = iClose(_Symbol, PERIOD_CURRENT, 0);
   double high0  = iHigh (_Symbol, PERIOD_CURRENT, 0);
   double low0   = iLow  (_Symbol, PERIOD_CURRENT, 0);
   if(open0 == 0) return 0;

   int neto0  = (int)((close0 - open0) / myPoint);
   int julat0 = (int)((high0  - low0)  / myPoint);
   double bH0 = MathMax(open0, close0), bL0 = MathMin(open0, close0);
   int atas0  = (int)((high0 - bH0) / myPoint);
   int bawah0 = (int)((bL0 - low0) / myPoint);

   int neto1 = 0, julat1 = 0, neto2 = 0, julat2 = 0, neto3 = 0, julat3 = 0;
   double high1=0, low1=0, high2=0, low2=0;
   for(int s = 1; s <= 3; s++)
   {
      double o = iOpen(_Symbol, PERIOD_CURRENT, s);
      double c = iClose(_Symbol, PERIOD_CURRENT, s);
      double h = iHigh(_Symbol, PERIOD_CURRENT, s);
      double l = iLow(_Symbol, PERIOD_CURRENT, s);
      if(o == 0) continue;
      int n = (int)((c - o) / myPoint);
      int j = (int)((h - l) / myPoint);
      if(s == 1) { neto1 = n; julat1 = j; high1 = h; low1 = l; }
      if(s == 2) { neto2 = n; julat2 = j; high2 = h; low2 = l; }
      if(s == 3) { neto3 = n; julat3 = j; }
   }

   double price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double jarakHigh = high0 - price;
   double jarakLow  = price - low0;
   int totalWick = atas0 + bawah0; if(totalWick <= 0) totalWick = 1;
   double imbalance = (double)(atas0 - bawah0) / totalWick;

   // --- Threshold adaptif (ATR) ---
   int momMin  = InpSigMomPts;
   int pullPts = InpSigPullbackPts;
   int rngMax  = InpSigRangePts;
   int baseMin = InpSigBasePts;
   int netoDMin = 4;
   int unit = GetSignalUnitPts();
   if(InpUseATRScale && unit > 0)
   {
      momMin   = MathMax(momMin,   (int)(unit * 0.5));
      pullPts  = MathMax(pullPts,  (int)(unit * 0.15));
      rngMax   = MathMax(rngMax,   (int)(unit * 0.6));
      baseMin  = MathMax(baseMin,  (int)(unit * 0.4));
      netoDMin = MathMax(netoDMin, (int)(unit * 0.25));
   }
   int jarakWickPts  = pullPts;
   int jarakRangePts = MathMax(12, (int)(rngMax * 0.4));

   // Sinyal A – Momentum Kuat
   if(MathAbs(neto0) >= momMin && MathAbs(neto1) >= 6 && (julat1 == 0 || julat0 > julat1 * 1.15))
   {
      if(neto0 > 0 && neto1 > 0)
      { label = "A_MOMENTUM_BUY"; score = 8 + MathMin(2, neto0 / 5); return 1; }
      if(neto0 < 0 && neto1 < 0)
      { label = "A_MOMENTUM_SELL"; score = 8 + MathMin(2, MathAbs(neto0) / 5); return -1; }
   }

   // Sinyal B – Pullback
   if(neto2 * neto3 > 0 && MathAbs(neto2) >= 5)
   {
      if(neto2 > 0 && neto0 <= 3 && jarakLow < jarakWickPts * myPoint)
      { label = "B_PULLBACK_BUY"; score = 7; return 1; }
      if(neto2 < 0 && neto0 >= -3 && jarakHigh < jarakWickPts * myPoint)
      { label = "B_PULLBACK_SELL"; score = 7; return -1; }
   }

   // Sinyal C – Range
   if((julat1 > 0 && julat1 < rngMax) && (julat2 == 0 || julat2 < (int)(rngMax * 1.1)) && (julat3 == 0 || julat3 < (int)(rngMax * 1.15)))
   {
      if(jarakLow < jarakRangePts * myPoint)
      { label = "C_RANGE_BUY"; score = 6; return 1; }
      if(jarakHigh < jarakRangePts * myPoint)
      { label = "C_RANGE_SELL"; score = 6; return -1; }
   }

   // Sinyal D – Imbalance
   if(MathAbs(imbalance) > 0.45 && MathAbs(neto0) >= netoDMin)
   {
      if(imbalance > 0.45 && neto0 < 0)
      { label = "D_PRESSURE_SELL"; score = 7; return -1; }
      if(imbalance < -0.45 && neto0 > 0)
      { label = "D_PRESSURE_BUY"; score = 7; return 1; }
   }

   // Sinyal E – Konvergensi 4 bar
   if((neto3 > 0 && neto2 > 0 && neto1 > 0 && neto0 > 0) ||
      (neto3 < 0 && neto2 < 0 && neto1 < 0 && neto0 < 0))
   {
      if(neto0 > 0) { label = "E_KONVERGENSI_BUY"; score = 9; return 1; }
      else          { label = "E_KONVERGENSI_SELL"; score = 9; return -1; }
   }

   // Dasar – Neto kuat
   if(MathAbs(neto0) >= baseMin)
   {
      if(neto0 > 0) { label = "DASAR_BUY"; score = 6; return 1; }
      else          { label = "DASAR_SELL"; score = 6; return -1; }
   }

   return 0;
}

//==================== STRATEGY 1: TROBOSAN BREAKOUT ====================
bool CheckBreakout(ENUM_POSITION_TYPE &signalType)
{
   double prevHigh = iHigh(_Symbol, InpGTTimeframe, 1);
   double prevLow  = iLow (_Symbol, InpGTTimeframe, 1);
   double price    = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(prevHigh == 0 || prevLow == 0) return false;
   if(price > prevHigh) { signalType = POSITION_TYPE_BUY;  return true; }
   if(price < prevLow)  { signalType = POSITION_TYPE_SELL; return true; }
   return false;
}

void LogicBreakout()
{
   g_activeStrategy = "BREAKOUT";
   if(!IsTradingAllowed()) return;
   if(CountMyPositions() > 0) return;

   if(InpRequireSignal)
   {
      int sc; string lb;
      int dir = EvaluateGTSignal(sc, lb);
      g_lastSignalType = lb; g_lastSignalScore = sc;
      if(dir == 0) return;
   }

   ENUM_POSITION_TYPE sig;
   if(CheckBreakout(sig))
      OpenPosition(sig, CalcNextLot(), "GT Trobosan " + (sig == POSITION_TYPE_BUY ? "BUY" : "SELL"));
}

//==================== STRATEGY 2: LAYER / GRID ====================
void LogicLayer()
{
   g_activeStrategy = "LAYER";
   if(!IsTradingAllowed()) return;
   int posCount = CountMyPositions();
   if(posCount >= InpMaxSteps) return;

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

   // Tentukan arah dari sinyal GT atau neto live
   int sc; string lb;
   int dir = EvaluateGTSignal(sc, lb);
   g_lastSignalType = lb; g_lastSignalScore = sc;

   ENUM_POSITION_TYPE prefer = POSITION_TYPE_BUY;
   if(dir < 0) prefer = POSITION_TYPE_SELL;
   else if(dir == 0)
   {
      double open0 = iOpen(_Symbol, PERIOD_CURRENT, 0);
      double close0 = iClose(_Symbol, PERIOD_CURRENT, 0);
      if(close0 < open0) prefer = POSITION_TYPE_SELL;
   }

   // Cari harga rata-rata posisi existing
   double avgPrice = 0, totalLots = 0;
   ENUM_POSITION_TYPE existingType = (ENUM_POSITION_TYPE)-1;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(!PositionSelectByTicket(ticket)) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != (long)InpMagic) continue;
      double lots = PositionGetDouble(POSITION_VOLUME);
      double px   = PositionGetDouble(POSITION_PRICE_OPEN);
      avgPrice += px * lots;
      totalLots += lots;
      existingType = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
   }

   if(totalLots > 0)
   {
      avgPrice /= totalLots;
      prefer = existingType; // lanjut layer searah
      double distPts = MathAbs((prefer == POSITION_TYPE_BUY ? bid : ask) - avgPrice) / myPoint;
      if(distPts < InpLayerStepPts) return; // belum cukup jauh untuk layer baru
   }

   double lot = NormalizeLot(InpLot * MathPow(InpMultiplier, posCount));
   if(lot > InpMaxLotCap) lot = NormalizeLot(InpMaxLotCap); // [v1.11] batas lot
   OpenPosition(prefer, lot, StringFormat("GT Layer #%d", posCount + 1));
}

//==================== STRATEGY 3: ZIGZAG BOUNCING ====================
void LogicZigzag()
{
   g_activeStrategy = "ZIGZAG";
   if(!IsTradingAllowed()) return;
   if(CountMyPositions() > 0) return;

   double bid  = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double high = iHigh(_Symbol, InpGTTimeframe, 1);
   double low  = iLow (_Symbol, InpGTTimeframe, 1);
   double open0 = iOpen(_Symbol, PERIOD_CURRENT, 0);
   double close0 = iClose(_Symbol, PERIOD_CURRENT, 0);
   if(high == 0 || low == 0) return;

   int bounce = InpZigzagBouncePts;
   // Bounce dari rendah → BUY ; bounce dari tinggi → SELL
   bool nearLow  = (bid - low)  <= bounce * myPoint;
   bool nearHigh = (high - bid) <= bounce * myPoint;

   // Konfirmasi reversal kecil (neto berlawanan arah ekstrem)
   int neto = (int)((close0 - open0) / myPoint);

   ENUM_POSITION_TYPE sig = (ENUM_POSITION_TYPE)-1;
   if(nearLow && neto >= -3)  // dekat low & tidak bearish keras
      sig = POSITION_TYPE_BUY;
   else if(nearHigh && neto <= 3)
      sig = POSITION_TYPE_SELL;

   if(sig == (ENUM_POSITION_TYPE)-1) return;

   if(InpRequireSignal)
   {
      int sc; string lb;
      int dir = EvaluateGTSignal(sc, lb);
      g_lastSignalType = lb; g_lastSignalScore = sc;
      if(dir == 0) return;
      if(dir > 0 && sig != POSITION_TYPE_BUY) return;
      if(dir < 0 && sig != POSITION_TYPE_SELL) return;
   }

   OpenPosition(sig, CalcNextLot(), "GT Zigzag " + (sig == POSITION_TYPE_BUY ? "BUY" : "SELL"));
}

//==================== STRATEGY 4: SINYAL GT A-E ====================
void LogicSignal()
{
   g_activeStrategy = "SIGNAL";
   if(!IsTradingAllowed()) return;
   if(CountMyPositions() > 0) return;

   int sc; string lb;
   int dir = EvaluateGTSignal(sc, lb);
   g_lastSignalType = lb;
   g_lastSignalScore = sc;

   if(dir == 0 || sc < 6) return; // minimal skor 6

   ENUM_POSITION_TYPE sig = (dir > 0) ? POSITION_TYPE_BUY : POSITION_TYPE_SELL;
   OpenPosition(sig, CalcNextLot(), "GT Sinyal " + lb);
}

//--- Dispatcher utama
void ExecuteTradingLogic()
{
   switch(InpStrategy)
   {
      case STRAT_LAYER:    LogicLayer();    break;
      case STRAT_ZIGZAG:   LogicZigzag();   break;
      case STRAT_SIGNAL:   LogicSignal();   break;
      case STRAT_BREAKOUT:
      default:             LogicBreakout(); break;
   }
}

// [v1.11] Tombol darurat: tutup semua posisi milik EA ini
void CloseMyPositions()
{
   int closed = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket))
         if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
            PositionGetInteger(POSITION_MAGIC) == (long)InpMagic)
            if(trade.PositionClose(ticket)) closed++;
   }
   if(closed > 0) Print("GT: Menutup ", closed, " posisi.");
}

//--- OnTradeTransaction: martingale step
// [v1.11] Di max step → berhenti (bukan reset) jika InpStopOnMaxStep=true
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest     &request,
                        const MqlTradeResult      &result)
{
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;
   ulong dealTicket = trans.deal;
   if(!HistoryDealSelect(dealTicket)) return;
   if(HistoryDealGetInteger(dealTicket, DEAL_MAGIC) != InpMagic) return;
   if(HistoryDealGetString (dealTicket, DEAL_SYMBOL) != _Symbol) return;

   ENUM_DEAL_ENTRY entry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(dealTicket, DEAL_ENTRY);
   if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_INOUT) return;

   double profit = HistoryDealGetDouble(dealTicket, DEAL_PROFIT) +
                   HistoryDealGetDouble(dealTicket, DEAL_SWAP) +
                   HistoryDealGetDouble(dealTicket, DEAL_COMMISSION);

   if(profit > 0)
   {
      g_martingaleStep = 0;
      Print("GT: Profit. Martingale/Layer reset ke 0.");
   }
   else if(profit < 0)
   {
      if(InpStopOnMaxStep && g_martingaleStep >= InpMaxSteps)
         return; // sudah di max step — tunggu profit, jangan tambah lagi

      g_martingaleStep++;
      if(g_martingaleStep >= InpMaxSteps)
      {
         if(InpStopOnMaxStep)
            Print("GT: Max step tercapai (", InpMaxSteps, "). Entry dihentikan sampai profit.");
         else
         {
            g_martingaleStep = 0;
            Print("GT: Max step tercapai (", InpMaxSteps, "). Reset.");
         }
      }
      else
         Print("GT: Loss. Step naik ke ", g_martingaleStep);
   }
}
//+------------------------------------------------------------------+

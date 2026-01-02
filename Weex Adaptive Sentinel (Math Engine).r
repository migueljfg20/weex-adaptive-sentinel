//@version=5
indicator("Weex Adaptive Sentinel (Math Engine)", overlay=true, max_lines_count=500, max_labels_count=500, max_boxes_count=500)

//----------------------------------------------------
// ⚙️ MASTER CONFIG (RESET SYSTEM)
//----------------------------------------------------
configProfile = input.string("Custom (Manual)", "⚙️ MODO DE OPERAÇÃO", options=["Standard (Default)", "Scalping (Aggressive)", "Custom (Manual)"], group="MASTER CONFIG", tooltip="Standard: Ignora os inputs e usa a configuração equilibrada original.\nScalping: Ignora os inputs e usa configuração rápida.\nCustom: Usa os valores que você digitar abaixo.")

//----------------------------------------------------
// INPUTS (COM RENOMEAÇÃO PARA PERMITIR RESET)
//----------------------------------------------------
// --- Fibonacci Inputs ---
useAdaptivePivot = input.bool(true, "Usar Pivot Adaptativo?", group="Fibonacci")
// Renomeados para _Input para podermos sobrepor com o Perfil
pivotManualLen_Input = input.int(10, "Período Pivot Manual", minval=1, group="Fibonacci")
pivotMinLen_Input = input.int(3, "Período Pivot Mínimo", minval=1, group="Fibonacci")
pivotMaxLen_Input = input.int(21, "Período Pivot Máximo", minval=1, group="Fibonacci")
atrLen_Input = input.int(20, "Período do ATR para Adaptar", minval=1, group="Fibonacci")
toleranceTicks = input.int(3, "Tolerância ao tocar nível (ticks)", group="Fibonacci")
max_fibs_to_keep = input.int(3, "Máximo de Fibonaccis a manter", minval=1, group="Fibonacci")
minSwingSizeTicks = input.int(50, "Tamanho Mínimo do Swing (ticks)", minval=1, group="Fibonacci")

// --- DMI/ADX Inputs ---
dmiLen = input.int(14, "DMI Length", group="Sinais de Disparo")
adxLen = input.int(14, "ADX Smoothing", group="Sinais de Disparo")
keyLevel = input.int(23, "ADX Key Level", group="Sinais de Disparo")
// Resetáveis:
convergenceThreshold_Input = input.float(10.0, "Limiar de Convergência DMI (%)", group="Sinais de Disparo")
squeezeLookback_Input = input.int(10, "Período de Procura", group="Sinais de Disparo")
atrFilterMultiplier_Input = input.float(0.5, "Filtro Volatilidade", group="Sinais de Disparo")
showInicioSignal = input.bool(true, "Mostrar Sinal de Início", group="Sinais de Disparo")
showContinuidadeSignal = input.bool(true, "Mostrar Continuidade", group="Sinais de Disparo")

// --- RSI & Divergências Inputs ---
confirmRSI = input.bool(true, "Exigir confirmação RSI (Fibo)?", group="RSI e Divergências")
// Resetáveis:
rsiLookbackWindow_Input = input.int(5, "Janela de Validade RSI (Barras)", minval=1, group="RSI e Divergências")
divLookback_Input = input.int(2, "Sensibilidade Divergência (Barras)", minval=1, group="RSI e Divergências")

rsiLen = input.int(14, "RSI Length", group="RSI e Divergências")
rsiSmaLen = input.int(9, "RSI SMA Length", group="RSI e Divergências")
showDivs = input.bool(true, "Mostrar Divergências RSI?", group="RSI e Divergências")
useStrictDiv = input.bool(false, "Usar Modo Estrito (Pivot RSI)?", group="RSI e Divergências")

// --- PAINEL ---
showTrendPanel = input.bool(true, "Mostrar Painel?", group="Painel")
trendEmaLen = input.int(200, "EMA Tendência", minval=1, group="Painel")
showMoonPanel = input.bool(true, "Mostrar Lua?", group="Painel")
panelSizeOption = input.string("Normal", "Tamanho Texto", options=["Pequeno", "Normal", "Grande"], group="Painel")

// --- POSICIONAMENTO ---
fiboPanel_x_offset = input.int(5, "Offset X Fibo", group="Posicionamento")
fiboPanel_y_offset = input.int(150, "Offset Y Fibo", group="Posicionamento")

//----------------------------------------------------
// LÓGICA DE RESET (DEFINIÇÃO DAS VARIÁVEIS FINAIS)
//----------------------------------------------------
// Aqui definimos as variáveis que o script vai realmente usar
var int pivotMinLen = na
var int pivotMaxLen = na
var int atrLen = na
var float convergenceThreshold = na
var int squeezeLookback = na
var float atrFilterMultiplier = na
var int rsiLookbackWindow = na
var int divLookback = na

if configProfile == "Standard (Default)"
    // Valores Originais (Equilibrados)
    pivotMinLen := 3
    pivotMaxLen := 21
    atrLen := 20
    convergenceThreshold := 10.0
    squeezeLookback := 10
    atrFilterMultiplier := 0.5
    rsiLookbackWindow := 5
    divLookback := 2

else if configProfile == "Scalping (Aggressive)"
    // Valores Rápidos
    pivotMinLen := 2
    pivotMaxLen := 10
    atrLen := 14
    convergenceThreshold := 15.0
    squeezeLookback := 5
    atrFilterMultiplier := 0.3
    rsiLookbackWindow := 3
    divLookback := 1

else
    // Valores Manuais (O que está na caixa)
    pivotMinLen := pivotMinLen_Input
    pivotMaxLen := pivotMaxLen_Input
    atrLen := atrLen_Input
    convergenceThreshold := convergenceThreshold_Input
    squeezeLookback := squeezeLookback_Input
    atrFilterMultiplier := atrFilterMultiplier_Input
    rsiLookbackWindow := rsiLookbackWindow_Input
    divLookback := divLookback_Input

//----------------------------------------------------
// CORES
//----------------------------------------------------
var color C_LEVEL_0=color.new(color.gray,0), var color C_LEVEL_236=color.new(color.green,60), var color C_LEVEL_382=color.new(color.green,40), var color C_LEVEL_5=color.new(color.red,20), var color C_LEVEL_618=#3ff4a1, var color C_LEVEL_786=color.new(color.blue,20), var color C_LEVEL_1=color.new(color.gray,0), var color C_LEVEL_NEG27=color.new(color.red,0)
uptrendColor = color.new(color.teal, 70)
downtrendColor = color.new(color.maroon, 70)
neutralColor = color.new(color.gray, 70)

//----------------------------------------------------
// VARIÁVEIS GLOBAIS
//----------------------------------------------------
var float swingHigh=na, var int swingHighBar=na, var float swingLow=na, var int swingLowBar=na, var int direction=0
var box[] fibBoxes=array.new_box(), var line[] fibLines=array.new_line(), var label[] fibLabels=array.new_label()

//----------------------------------------------------
// CAPTURA DOS SWINGS
//----------------------------------------------------
int len = 0
if useAdaptivePivot
    float currentAtr = ta.atr(atrLen) // Usa a variável do perfil
    float highestAtr = ta.highest(currentAtr, 50)
    float lowestAtr = ta.lowest(currentAtr, 50)
    float normalizedAtr = (highestAtr - lowestAtr > 0) ? (currentAtr - lowestAtr) / (highestAtr - lowestAtr) : 0
    len := math.round(pivotMinLen + (pivotMaxLen - pivotMinLen) * normalizedAtr) // Usa variáveis do perfil
else
    len := pivotManualLen_Input

// Detecção dos Pivots
ph = ta.pivothigh(high, len, len)
pl = ta.pivotlow(low, len, len)

// Atualização dos Swings
if not na(ph)
    swingHigh := ph
    swingHighBar := bar_index - len

if not na(pl)
    swingLow := pl
    swingLowBar := bar_index - len

// --- CORREÇÃO DE ESTRUTURA ---
if not na(swingLow) and low < swingLow
    swingLow := na
    swingLowBar := na

if not na(swingHigh) and high > swingHigh
    swingHigh := na
    swingHighBar := na

// Definição da Direção
if not na(swingHigh) and not na(swingLow)
    if swingLowBar < swingHighBar
        direction := 1 // Bullish
    else
        direction := -1 // Bearish
else
    direction := 0

//----------------------------------------------------
// CÁLCULO RSI E SINAIS FIBO
//----------------------------------------------------
rsi = ta.rsi(close, rsiLen)
rsiSma = ta.sma(rsi, rsiSmaLen)
rsiBuyCond = ta.crossover(rsi, rsiSma)
rsiSellCond = ta.crossunder(rsi, rsiSma)

bool rsiBuyRecent = ta.barssince(rsiBuyCond) < rsiLookbackWindow // Usa variável do perfil
bool rsiSellRecent = ta.barssince(rsiSellCond) < rsiLookbackWindow // Usa variável do perfil

tolerance = toleranceTicks * syminfo.mintick
float current_n618 = na

if direction == 1
    current_n618 := swingHigh - (swingHigh - swingLow) * 0.618
else if direction == -1
    current_n618 := swingLow + (swingHigh - swingLow) * 0.618

touch618 = not na(current_n618) and (low <= current_n618 + tolerance and high >= current_n618 - tolerance)
bool isSwingBigEnough = not na(swingHigh) and not na(swingLow) ? (math.abs(swingHigh - swingLow) / syminfo.mintick) >= minSwingSizeTicks : false

bool signalFiboBuy = (direction == 1) and touch618 and (not confirmRSI or rsiBuyRecent) and isSwingBigEnough
bool signalFiboSell = (direction == -1) and touch618 and (not confirmRSI or rsiSellRecent) and isSwingBigEnough

//----------------------------------------------------
// DIVERGÊNCIAS
//----------------------------------------------------
// Usa divLookback do perfil
plPrice = ta.pivotlow(low, divLookback, divLookback)
phPrice = ta.pivothigh(high, divLookback, divLookback)
plRsi = ta.pivotlow(rsi, divLookback, divLookback)
phRsi = ta.pivothigh(rsi, divLookback, divLookback)

var float lastPlPrice = na
var float lastPlRsiValue = na
var float lastPhPrice = na
var float lastPhRsiValue = na

bool bullDiv = false
bool bearDiv = false

if not na(plPrice)
    bool rsiConditionMet = useStrictDiv ? not na(plRsi) : true
    if rsiConditionMet and not na(lastPlPrice)
        float currentRsiVal = rsi[divLookback] 
        if low[divLookback] < lastPlPrice and currentRsiVal > lastPlRsiValue
            bullDiv := true
    lastPlPrice := low[divLookback]
    lastPlRsiValue := rsi[divLookback]

if not na(phPrice)
    bool rsiConditionMet = useStrictDiv ? not na(phRsi) : true
    if rsiConditionMet and not na(lastPhPrice)
        float currentRsiVal = rsi[divLookback]
        if high[divLookback] > lastPhPrice and currentRsiVal < lastPhRsiValue
            bearDiv := true
    lastPhPrice := high[divLookback]
    lastPhRsiValue := rsi[divLookback]

//----------------------------------------------------
// LÓGICA MESTRA DE SINAIS (FIBO + DIVERGÊNCIAS)
//----------------------------------------------------

// Combos
bool isComboBuy = signalFiboBuy and bullDiv
bool isComboSell = signalFiboSell and bearDiv

// Gatilhos Finais (Um OU Outro)
bool masterBuy = signalFiboBuy or bullDiv
bool masterSell = signalFiboSell or bearDiv

// Limitar sinal a uma vez por barra (evita repetição visual)
var int lastBuyBar = na
var int lastSellBar = na

if masterBuy
    if bar_index == lastBuyBar
        masterBuy := false
    else
        lastBuyBar := bar_index

if masterSell
    if bar_index == lastSellBar
        masterSell := false
    else
        lastSellBar := bar_index

// Definição da RAZÃO para a AI (JSON)
string reasonBuy = "Generic"
if isComboBuy
    reasonBuy := "COMBO PERFECT (Fibo + Div)"
else if signalFiboBuy
    reasonBuy := "Fibo Structure 0.618"
else if bullDiv
    reasonBuy := "RSI Bullish Divergence"

string reasonSell = "Generic"
if isComboSell
    reasonSell := "COMBO PERFECT (Fibo + Div)"
else if signalFiboSell
    reasonSell := "Fibo Structure 0.618"
else if bearDiv
    reasonSell := "RSI Bearish Divergence"

//----------------------------------------------------
// SINAIS DMI/ADX (Auxiliares)
//----------------------------------------------------
[plusDI, minusDI, adx] = ta.dmi(dmiLen, adxLen)
// Usa convergenceThreshold do perfil
bool squeezeCondition = adx < keyLevel and math.abs(plusDI - minusDI) < convergenceThreshold
bool wasSqueezing = false
// Usa squeezeLookback do perfil
for i = 1 to squeezeLookback
    if squeezeCondition[i]
        wasSqueezing := true
        break
var int dmiDirectionBias = 0
if ta.crossover(plusDI, minusDI)
    dmiDirectionBias := 1
if ta.crossunder(plusDI, minusDI)
    dmiDirectionBias := -1
bool adxBreakoutTrigger = wasSqueezing and ta.crossover(adx, keyLevel)
bool bullishAdxBreakout = adxBreakoutTrigger and dmiDirectionBias == 1
bool bearishAdxBreakout = adxBreakoutTrigger and dmiDirectionBias == -1
var float squeezeHigh = na, var float squeezeLow = na
if wasSqueezing
    squeezeHigh := ta.highest(high, squeezeLookback)
    squeezeLow := ta.lowest(low, squeezeLookback)
atrValue = ta.atr(14)
// Usa atrFilterMultiplier do perfil
minRangeSize = atrValue * atrFilterMultiplier
bool bullishPriceBreakout = wasSqueezing[1] and (squeezeHigh[1] - squeezeLow[1] > minRangeSize) and ta.crossover(close, squeezeHigh[1])
bool bearishPriceBreakout = wasSqueezing[1] and (squeezeHigh[1] - squeezeLow[1] > minRangeSize) and ta.crossunder(close, squeezeLow[1])

//----------------------------------------------------
// DESENHO DAS FIBONACCIS
//----------------------------------------------------
if masterBuy or masterSell
    // Desenha Fibo apenas se o sinal vier de Fibo ou Combo (Div sozinhas não redesenham a régua)
    if signalFiboBuy or signalFiboSell
        float fibDrawStart = direction == 1 ? swingHigh : swingLow
        float fibDrawEnd = direction == 1 ? swingLow : swingHigh
        
        int t1 = math.min(swingHighBar, swingLowBar)
        int t2 = math.max(swingHighBar, swingLowBar)
        
        float n0 = fibDrawStart, n1 = fibDrawEnd
        float n236 = n0 + (n1 - n0) * 0.236
        float n382 = n0 + (n1 - n0) * 0.382
        float n5 = n0 + (n1 - n0) * 0.5
        float n618 = n0 + (n1 - n0) * 0.618
        float n786 = n0 + (n1 - n0) * 0.786
        float nNeg27 = n0 + (n1 - n0) * -0.27
        
        array.push(fibBoxes, box.new(t1, n0, t2, n1, border_color=na, bgcolor=color.new(color.gray, 85)))
        array.push(fibLines, line.new(t1, n0, t2, n0, color=C_LEVEL_0, width=2)), array.push(fibLabels, label.new(t2, n0, text="0 (" + str.tostring(n0, format.mintick) + ")", style=label.style_label_left, color=#00000000, textcolor=C_LEVEL_0, size=size.small))
        array.push(fibLines, line.new(t1, n236, t2, n236, color=C_LEVEL_236, width=2)), array.push(fibLabels, label.new(t2, n236, text="0.236 (" + str.tostring(n236, format.mintick) + ")", style=label.style_label_left, color=#00000000, textcolor=C_LEVEL_236, size=size.small))
        array.push(fibLines, line.new(t1, n382, t2, n382, color=C_LEVEL_382, width=2)), array.push(fibLabels, label.new(t2, n382, text="0.382 (" + str.tostring(n382, format.mintick) + ")", style=label.style_label_left, color=#00000000, textcolor=C_LEVEL_382, size=size.small))
        array.push(fibLines, line.new(t1, n5, t2, n5, color=C_LEVEL_5, width=2)), array.push(fibLabels, label.new(t2, n5, text="0.5 (" + str.tostring(n5, format.mintick) + ")", style=label.style_label_left, color=#00000000, textcolor=C_LEVEL_5, size=size.small))
        array.push(fibLines, line.new(t1, n618, t2, n618, color=C_LEVEL_618, width=2)), array.push(fibLabels, label.new(t2, n618, text="0.618 (" + str.tostring(n618, format.mintick) + ")", style=label.style_label_left, color=#00000000, textcolor=C_LEVEL_618, size=size.small))
        array.push(fibLines, line.new(t1, n786, t2, n786, color=C_LEVEL_786, width=2)), array.push(fibLabels, label.new(t2, n786, text="0.786 (" + str.tostring(n786, format.mintick) + ")", style=label.style_label_left, color=#00000000, textcolor=C_LEVEL_786, size=size.small))
        array.push(fibLines, line.new(t1, n1, t2, n1, color=C_LEVEL_1, width=2)), array.push(fibLabels, label.new(t2, n1, text="1 (" + str.tostring(n1, format.mintick) + ")", style=label.style_label_left, color=#00000000, textcolor=C_LEVEL_1, size=size.small))
        array.push(fibLines, line.new(t1, nNeg27, t2, nNeg27, color=C_LEVEL_NEG27, width=2)), array.push(fibLabels, label.new(t2, nNeg27, text="-0.27 (" + str.tostring(nNeg27, format.mintick) + ")", style=label.style_label_left, color=#00000000, textcolor=C_LEVEL_NEG27, size=size.small))

        if array.size(fibBoxes) > max_fibs_to_keep
            box.delete(array.shift(fibBoxes))
            for i = 1 to 8
                line.delete(array.shift(fibLines))
                label.delete(array.shift(fibLabels))

//----------------------------------------------------
// PLOTAGENS FINAIS (VISUAL ESTRATÉGICO)
//----------------------------------------------------

// Cores
colFibo = color.new(color.green, 0)
colDiv  = color.new(color.blue, 0)
colCombo = color.new(color.purple, 0)
colSell = color.new(color.red, 0)

// --- PLOTS DE COMPRA ---
// 1. Combo (O mais forte)
plotshape(isComboBuy, title="Combo Buy", style=shape.labelup, location=location.belowbar, color=colCombo, textcolor=color.white, text="COMBO\n🚀", size=size.small)
// 2. Só Fibo
plotshape(signalFiboBuy and not bullDiv, title="Fibo Buy", style=shape.labelup, location=location.belowbar, color=colFibo, textcolor=color.white, text="FIBO", size=size.small)
// 3. Só Divergência
plotshape(bullDiv and not signalFiboBuy, title="Div Buy", style=shape.labelup, location=location.belowbar, color=colDiv, textcolor=color.white, text="DIV", size=size.small)

// --- PLOTS DE VENDA ---
// 1. Combo
plotshape(isComboSell, title="Combo Sell", style=shape.labeldown, location=location.abovebar, color=colCombo, textcolor=color.white, text="COMBO\n🔻", size=size.small)
// 2. Só Fibo
plotshape(signalFiboSell and not bearDiv, title="Fibo Sell", style=shape.labeldown, location=location.abovebar, color=colSell, textcolor=color.white, text="FIBO", size=size.small)
// 3. Só Divergência
plotshape(bearDiv and not signalFiboSell, title="Div Sell", style=shape.labeldown, location=location.abovebar, color=color.orange, textcolor=color.white, text="DIV", size=size.small)

// Plots Auxiliares
plotshape(series=showInicioSignal and bullishPriceBreakout, title="Início (Alta)", style=shape.diamond, location=location.belowbar, color=color.new(color.lime, 40), size=size.small, text="Início\n(Alta)")
plotshape(series=showInicioSignal and bearishPriceBreakout, title="Início (Baixa)", style=shape.diamond, location=location.abovebar, color=color.new(color.orange, 40), size=size.small, text="Início\n(Baixa)")
plotshape(series=showContinuidadeSignal and bullishAdxBreakout, title="Cont. (Alta)", style=shape.arrowup, location=location.belowbar, color=color.new(color.green, 0), size=size.tiny, text="Continuidade")
plotshape(series=showContinuidadeSignal and bearishAdxBreakout, title="Cont. (Baixa)", style=shape.arrowdown, location=location.abovebar, color=color.new(color.red, 0), size=size.tiny, text="Continuidade")

emaTendencia = ta.ema(close, trendEmaLen)
plot(series=emaTendencia, title="EMA de Tendência", color=showTrendPanel ? color.new(color.orange, 40) : na, linewidth=2)

//----------------------------------------------------
// CÁLCULO DE STATUS DA TENDÊNCIA (Movido para cima para uso nos alertas)
//----------------------------------------------------
var int trendStatus = 0
var int trendStartTime = na

if close > emaTendencia and trendStatus != 1
    trendStatus := 1
    trendStartTime := time
else if close < emaTendencia and trendStatus != -1
    trendStatus := -1
    trendStartTime := time
if na(trendStatus)
    trendStatus := close > emaTendencia ? 1 : -1
    trendStartTime := time

//----------------------------------------------------
// ALERTAS JSON PARA O BOT PYTHON (ENRIQUECIDOS)
//----------------------------------------------------

//----------------------------------------------------
// PREPARAÇÃO DE PREÇOS TÉCNICOS (SL & TP MÚLTIPLOS)
//----------------------------------------------------
float dynamicSL = na
float dynamicTP1 = na // O nível 0 (Conservador / Scalping)
float dynamicTP2 = na // O nível -0.27 (Alvo Final)

// Lógica para COMPRA
if masterBuy
    dynamicSL := swingLow            // Stop no fundo anterior
    dynamicTP1 := swingHigh          // TP1: O Topo anterior (Nível 0) -> Garantir lucro rápido
    dynamicTP2 := swingHigh + (swingHigh - swingLow) * 0.27 // TP2: Extensão -0.27

// Lógica para VENDA
else if masterSell
    dynamicSL := swingHigh           // Stop no topo anterior
    dynamicTP1 := swingLow           // TP1: O Fundo anterior (Nível 0)
    dynamicTP2 := swingLow - (swingHigh - swingLow) * 0.27 // TP2: Extensão -0.27

//----------------------------------------------------
// ALERTAS JSON PARA O BOT PYTHON (AGORA COM TP1 e TP2)
//----------------------------------------------------
// Prepara dados extras para a IA julgar melhor
string adxStatus = str.tostring(adx, "#.##")
string trendStatusMsg = trendStatus == 1 ? "Uptrend" : "Downtrend"
string volatilityState = wasSqueezing ? "Squeeze Breakout" : "Normal"

// Formata preços para string
string slStr = str.tostring(dynamicSL, format.mintick)
string tp1Str = str.tostring(dynamicTP1, format.mintick)
string tp2Str = str.tostring(dynamicTP2, format.mintick)

// Payload agora inclui tp1 (Conservador) e tp2 (Agressivo)
if masterBuy
    alert('{"ticker": "' + syminfo.ticker + '", "action": "buy", "reason": "' + reasonBuy + '", "price": ' + str.tostring(close) + ', "adx": ' + adxStatus + ', "trend": "' + trendStatusMsg + '", "volatility": "' + volatilityState + '", "sl": ' + slStr + ', "tp1": ' + tp1Str + ', "tp2": ' + tp2Str + '}', alert.freq_once_per_bar)

if masterSell
    alert('{"ticker": "' + syminfo.ticker + '", "action": "sell", "reason": "' + reasonSell + '", "price": ' + str.tostring(close) + ', "adx": ' + adxStatus + ', "trend": "' + trendStatusMsg + '", "volatility": "' + volatilityState + '", "sl": ' + slStr + ', "tp1": ' + tp1Str + ', "tp2": ' + tp2Str + '}', alert.freq_once_per_bar)
//----------------------------------------------------
// PAINEL DE INFORMAÇÃO
//----------------------------------------------------
var label infoPanel = na
if barstate.islast and not na(swingHigh) and not na(swingLow)
    string startText = str.tostring(swingHigh, format.mintick)
    string endText = str.tostring(swingLow, format.mintick)
    string fibLevelText = not na(current_n618) ? "\n0.618: " + str.tostring(current_n618, format.mintick) : "\nQuebra de Estrutura"
    
    infoText = "Start: " + startText + "\nEnd: " + endText + fibLevelText
    label.delete(infoPanel)
    float panelYAnchor = math.max(swingHigh, swingLow)
    infoPanel := label.new(x=bar_index + fiboPanel_x_offset, y=panelYAnchor + (fiboPanel_y_offset * syminfo.mintick), text=infoText, xloc=xloc.bar_index, yloc=yloc.price, style=label.style_label_right, textcolor=color.white, color=color.new(color.blue, 70), textalign=text.align_left)

var table mainPanelTable = na
textSize = panelSizeOption == "Pequeno" ? size.small : panelSizeOption == "Normal" ? size.normal : size.large

if barstate.islast
    if na(mainPanelTable)
        mainPanelTable := table.new(position.bottom_left, 1, 1, border_width=1)
    
    string trendText = ""
    if showTrendPanel
        string statusStr = trendStatus == 1 ? "Tendência de Alta" : "Tendência de Baixa"
        string dateStr = na(trendStartTime) ? "" : str.format("{0,date,dd-MMM HH:mm}", trendStartTime)
        trendText := statusStr + "\nDesde: " + dateStr
    
    string moonText = ""
    if showMoonPanel
        int EPOCH_2024 = timestamp("UTC", 2024, 1, 11, 11, 57) 
        float MEAN_LUNAR_MONTH = 29.53059
        float HALF_CYCLE = MEAN_LUNAR_MONTH / 2 
        float msSinceEpoch = time_close - EPOCH_2024
        float daysSinceEpoch = msSinceEpoch / (1000 * 60 * 60 * 24)
        float moonAgeRaw = daysSinceEpoch % MEAN_LUNAR_MONTH
        float moonAge = moonAgeRaw >= 0 ? moonAgeRaw : moonAgeRaw + MEAN_LUNAR_MONTH
        
        string phaseName = ""
        string phaseIcon = ""
        
        if moonAge < 1.5 or moonAge > 28.5
            phaseName := "Lua Nova"
            phaseIcon := "🌑"
        else if moonAge >= 1.5 and moonAge < 6.5
            phaseName := "Crescente"
            phaseIcon := "🌒"
        else if moonAge >= 6.5 and moonAge < 8.5
            phaseName := "Quarto Crescente"
            phaseIcon := "🌓"
        else if moonAge >= 8.5 and moonAge < 13.5
            phaseName := "Gibosa Crescente"
            phaseIcon := "🌔"
        else if moonAge >= 13.5 and moonAge < 16.0
            phaseName := "Lua Cheia"
            phaseIcon := "🌕"
        else if moonAge >= 16.0 and moonAge < 21.0
            phaseName := "Gibosa Minguante"
            phaseIcon := "🌖"
        else if moonAge >= 21.0 and moonAge < 23.5
            phaseName := "Quarto Minguante"
            phaseIcon := "🌗"
        else 
            phaseName := "Minguante"
            phaseIcon := "🌘"
            
        string countdownText = ""
        if moonAge < HALF_CYCLE
            float daysToFull = HALF_CYCLE - moonAge
            countdownText := str.format("\n{0,number,#.##} dias para 🌕", daysToFull)
        else
            float daysToNew = MEAN_LUNAR_MONTH - moonAge
            countdownText := str.format("\n{0,number,#.##} dias para 🌑", daysToNew)

        string separator = showTrendPanel ? "\n\n" : ""
        moonText := separator + phaseIcon + " " + phaseName + countdownText

    string finalPanelText = trendText + moonText
    color panelColor = showTrendPanel ? (trendStatus == 1 ? uptrendColor : downtrendColor) : neutralColor
    
    table.cell(mainPanelTable, 0, 0, finalPanelText, text_color=color.white, bgcolor=panelColor, text_halign=text.align_left, text_size=textSize, width=0, height=0)
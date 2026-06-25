const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, ImageRun,
        AlignmentType, HeadingLevel, LevelFormat, BorderStyle, WidthType, ShadingType,
        TableOfContents, PageBreak, Footer, PageNumber } = require("docx");

const FONT = "PingFang TC";
const CW = 9360; // content width (US Letter, 1" margins)
const A = "manual_assets/";

// ---- helpers ----
const H1 = t => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)] });
const H2 = t => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] });
const P = (t, o = {}) => new Paragraph({ spacing: { after: 120 }, children: Array.isArray(t) ? t : [new TextRun({ text: t, ...o })] });
const B = t => new Paragraph({ numbering: { reference: "b", level: 0 }, spacing: { after: 60 }, children: Array.isArray(t) ? t : [new TextRun(t)] });
const STEP = t => new Paragraph({ numbering: { reference: "steps", level: 0 }, spacing: { before: 120, after: 80 }, children: Array.isArray(t) ? t : [new TextRun({ text: t, bold: true })] });
const run = (t, o = {}) => new TextRun({ text: t, ...o });
function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) }; // PNG IHDR
}
function IMG(file, w = 560) {
  const s = pngSize(file);
  let W = w, H = Math.round(w * s.h / s.w); // 保留實際長寬比,不壓變形
  const HMAX = 600;                          // 限高,避免過長截圖撐爆版面
  if (H > HMAX) { H = HMAX; W = Math.round(HMAX * s.w / s.h); }
  return new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 140, after: 40 },
    children: [new ImageRun({ type: "png", data: fs.readFileSync(file), transformation: { width: W, height: H },
      altText: { title: "MacVitals 畫面", description: "MacVitals 操作畫面截圖", name: "screenshot" } })] });
}
function IMGfull(file, w = 460) {
  const h = Math.round(w * 1.344);
  return new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 140, after: 40 },
    children: [new ImageRun({ type: "png", data: fs.readFileSync(file), transformation: { width: w, height: h },
      altText: { title: "MacVitals 報告", description: "完整報告截圖", name: "screenshot" } })] });
}
const CAP = t => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 220 },
  children: [new TextRun({ text: "▲ " + t, italics: true, size: 18, color: "777777" })] });

const border = { style: BorderStyle.SINGLE, size: 1, color: "C9D3E0" };
const borders = { top: border, bottom: border, left: border, right: border };
function cell(text, width, { head = false, bold = false } = {}) {
  return new TableCell({ borders, width: { size: width, type: WidthType.DXA },
    shading: head ? { fill: "1F4E79", type: ShadingType.CLEAR } : { fill: "FFFFFF", type: ShadingType.CLEAR },
    margins: { top: 70, bottom: 70, left: 130, right: 130 },
    children: [new Paragraph({ children: [new TextRun({ text, bold: head || bold, color: head ? "FFFFFF" : "222222", size: 20 })] })] });
}
function table(widths, rows) {
  return new Table({ width: { size: CW, type: WidthType.DXA }, columnWidths: widths,
    rows: rows.map((r, i) => new TableRow({ tableHeader: i === 0,
      children: r.map((c, j) => cell(c, widths[j], { head: i === 0 })) })) });
}

const children = [];

// ===== 封面 =====
children.push(new Paragraph({ spacing: { before: 1600, after: 0 }, alignment: AlignmentType.CENTER,
  children: [new TextRun({ text: "MacVitals", bold: true, size: 72, color: "0F6FB5" })] }));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 },
  children: [new TextRun({ text: "macOS 健康體檢 — 使用手冊", size: 32, color: "333333" })] }));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 320 },
  children: [new TextRun({ text: "給所有人的操作說明(不需要懂電腦指令)", size: 22, color: "777777" })] }));
children.push(IMG(A + "01_landing.png", 460));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 320 },
  children: [new TextRun({ text: "版本 1.1", size: 20, color: "999999" })] }));
children.push(new Paragraph({ children: [new PageBreak()] }));

// ===== 目錄 =====
children.push(H1("目錄"));
children.push(new TableOfContents("目錄", { hyperlink: true, headingStyleRange: "1-2" }));
children.push(new Paragraph({ children: [new PageBreak()] }));

// ===== 1. 這是什麼 =====
children.push(H1("一、MacVitals 是什麼?"));
children.push(P("MacVitals 是一個幫你的 Mac 做「健康體檢」的小工具。就像人去做健康檢查一樣,它會一次幫你檢查電腦的十一個面向,告訴你哪裡正常、哪裡需要注意,並且對常見的小問題提供「一鍵修復」。"));
children.push(P([run("最重要的一點:", { bold: true }), run("整個檢查過程是「唯讀」的——它只是「看」,不會刪除、搬移或改動你的任何檔案。只有在你自己按下修復按鈕、並再次確認之後,它才會動手處理那一項。")]));
children.push(H2("它會檢查哪十一個面向?"));
children.push(table([1100, 2600, 5660], [
  ["代號", "檢查項目", "白話說明:它在看什麼"],
  ["M1", "重複檔案", "找出內容一模一樣的檔案副本,留一份就好、其餘可省空間"],
  ["M2", "損壞項目", "失效的捷徑與 Homebrew 設定(大多是正常的,會幫你分類)"],
  ["M3", "大型檔案", "佔空間的大檔案(超過 100MB),並說明每個檔案是做什麼的"],
  ["M4", "開發環境", "開發工具的版本是否過舊、是否該更新"],
  ["M5", "可回收空間", "各種快取/暫存,清掉可以釋放多少空間"],
  ["M6", "電池", "電池的循環次數、最大容量與健康狀態"],
  ["M7", "系統健康", "硬碟健康(SMART)、可用空間、記憶體與系統快照"],
  ["M8", "登入與背景", "開機時自動啟動的程式(太多會拖慢開機)"],
  ["M9", "安全與更新", "防火牆、加密(FileVault)、系統更新等安全設定"],
  ["M10", "近期當機", "你的 App 與系統最近有沒有常常閃退/當機,有沒有嚴重的核心崩潰(kernel panic)"],
  ["M11", "分享與遠端存取", "有沒有開著「別人可連進這台 Mac」的功能(遠端登入、螢幕共享、檔案分享)與自動登入"],
]));
children.push(new Paragraph({ spacing: { after: 120 } }));

// ===== 2. 開始之前 =====
children.push(H1("二、開始之前(需要準備什麼)"));
children.push(B([run("一台 Mac(macOS)。", {})]));
children.push(B([run("首次使用可能需要安裝 Apple 的「開發者工具」", { bold: true }), run(":若程式提示,按「安裝」,完成後再操作一次即可(只需一次)。")]));
children.push(B([run("大約預留 5–10 分鐘", { bold: true }), run(":全機掃描需要一點時間,尤其硬碟較大時。")]));
children.push(P([run("安全保證:", { bold: true, color: "0F6FB5" }), run("掃描階段全程唯讀,不會更動你的檔案;所有「修復」都需要你親自點擊並確認,而且程式會在執行的當下重新檢查一次現況,確保不會誤動。")]));

// ===== 3. 如何使用 =====
children.push(H1("三、如何使用(四個步驟)"));
children.push(STEP("步驟 1:雙擊「開始體檢」"));
children.push(P("在資料夾裡找到「開始體檢.command」這個檔案,用滑鼠左鍵連點兩下(雙擊)。電腦會打開一個黑色小視窗,並自動開啟瀏覽器。"));
children.push(P([run("小提醒:", { bold: true }), run("如果第一次出現「無法打開,因為來自未識別的開發者」,請",), run("按住鍵盤的 Control 鍵、再用滑鼠點一下該檔案", { bold: true }), run(",選「打開」,再按一次「打開」即可(只需一次)。過程中那個黑色視窗請不要關閉,關掉程式就停止了。")]));

children.push(STEP("步驟 2:在網頁上按「開始體檢」"));
children.push(P("瀏覽器會出現下面這個畫面。按下中間藍色的「開始體檢」按鈕。"));
children.push(IMG(A + "01_landing.png"));
children.push(CAP("MacVitals 首頁:按「開始體檢」即可開始"));

children.push(STEP("步驟 3:等待掃描完成"));
children.push(P("按下後會出現進度條,並顯示目前正在檢查哪一項(例如「掃描 M3…」)。請耐心等候,通常數分鐘內完成。"));
children.push(IMG(A + "02_progress.png"));
children.push(CAP("掃描進行中:進度條會顯示目前進度"));

children.push(STEP("步驟 4:自動看報告"));
children.push(P("掃描完成後,網頁會自動跳到一份「體檢報告」。看完、需要的修復也都處理完之後,把那個黑色視窗關閉就結束了。"));

// ===== 4. 報告怎麼看 =====
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(H1("四、報告怎麼看"));
children.push(P("報告的第一頁是「摘要」,把整台電腦的狀況濃縮在這裡。由上而下分成幾個區塊:"));
children.push(B([run("十一個檢查模組一覽:", { bold: true }), run("一排卡片,一眼看完每個面向的結果。點任一張卡片可以跳到該項目看細節。")]));
children.push(B([run("整體判讀:", { bold: true }), run("一句話總結這台電腦目前的狀態。")]));
children.push(B([run("需要你注意的事:", { bold: true }), run("依重要性排序的待辦清單,右邊就是「修復」按鈕。")]));
children.push(B([run("運作良好的部分:", { bold: true }), run("已經正常、不用擔心的項目。")]));
children.push(B([run("修復涵蓋範圍:", { bold: true }), run("可展開的完整對照表(本手冊第六章會詳列)。")]));
children.push(IMG(A + "03_report_summary.png"));
children.push(CAP("報告摘要頁上半部:模組一覽 + 整體判讀"));

children.push(H2("顏色代表什麼?"));
children.push(B([run("紅色 = 高風險,建議盡快處理", { bold: true, color: "B00020" }), run("(例如防火牆沒開)。")]));
children.push(B([run("黃色 = 中等,建議處理", { bold: true, color: "9A6700" }), run("(例如有套件可更新)。")]));
children.push(B([run("藍色 = 參考,可選優化", { bold: true, color: "0F6FB5" }), run("(例如可回收的快取)。")]));
children.push(B([run("綠色 = 運作良好,無需處理。", { bold: true, color: "1B7F4B" })]));

children.push(H2("想看某一項的細節?"));
children.push(P("點上方的分頁(M1～M11)即可看該項目的明細。例如「M3 大型檔案」會列出每個大檔,還會用白話告訴你「這是什麼」,方便你判斷能不能刪。"));
children.push(IMG(A + "05_module_m3.png"));
children.push(CAP("M3 大型檔案:每個檔案都附白話用途說明"));

// ===== 5. 一鍵修復 =====
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(H1("五、一鍵修復怎麼用"));
children.push(P("在「需要你注意的事」區塊,每一項右邊可能有一顆有顏色的「修復」按鈕(例如「一鍵清理快取」「更新 npm」),以及一顆「查看」按鈕。"));
children.push(IMG(A + "06_attention.png"));
children.push(CAP("「需要你注意的事」:右側即修復按鈕"));
children.push(H2("操作方式"));
const s2 = t => new Paragraph({ numbering: { reference: "steps2", level: 0 }, spacing: { after: 60 }, children: [new TextRun(t)] });
children.push(s2("按下你想處理的那一項的修復按鈕。"));
children.push(s2("會跳出一個確認視窗,說明將要做什麼。確定就按「確定」。"));
children.push(s2("若該項需要權限(例如開啟防火牆),macOS 會跳出輸入密碼的視窗,輸入你的開機密碼即可。"));
children.push(s2("畫面右下角會跳出結果訊息(例如釋出了多少空間)。"));
children.push(P([run("安心使用:", { bold: true, color: "0F6FB5" }), run("修復只會做「白名單」內的安全動作;而且程式會在按下的當下重新確認現況——如果其實沒事可做(例如防火牆其實已經開了),它只會回報「無需變更」,不會亂動。")]));
children.push(P([run("哪些不會幫你一鍵做?", { bold: true }), run("刪除重複檔、停用開機自啟程式這類「需要你自己判斷取捨」的,以及電池老化、硬碟異常這類「硬體問題」,MacVitals 只會提醒與導引,不會替你動手。")]));

// ===== 6. 修復範疇 =====
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(H1("六、掃描後的修復範疇"));
children.push(P("MacVitals 會依「當次掃描結果」決定要顯示哪些修復按鈕——掃到問題才會出現對應按鈕,沒問題就不會出現。下表是全部可能的對照(共涵蓋各模組的可行動發現):"));
children.push(table([1500, 3360, 4500], [
  ["檢查面向", "可能偵測到的問題", "MacVitals 的處理方式"],
  ["M9 安全", "防火牆未開啟", "一鍵開啟(需輸入密碼)"],
  ["M9 安全", "FileVault 磁碟加密未開", "開啟加密設定頁,引導你開啟"],
  ["M9 安全", "Gatekeeper 已關閉", "一鍵啟用(需輸入密碼)"],
  ["M9 安全", "SIP 系統保護已關閉", "提醒(需重開機進復原模式,不一鍵)"],
  ["M9 更新", "有系統更新待安裝", "一鍵開啟系統「軟體更新」頁"],
  ["M11 分享", "遠端登入(SSH)開著", "一鍵關閉遠端登入"],
  ["M11 分享", "螢幕共享開著", "一鍵關閉螢幕共享"],
  ["M4 開發", "Homebrew 套件過舊", "一鍵升級全部套件"],
  ["M4 開發", "pip 版本過舊", "一鍵更新 pip(不動系統 Python)"],
  ["M4 開發", "npm 全域套件過舊", "一鍵更新 npm"],
  ["M5 空間", "快取可回收(>300MB)", "一鍵清理安全快取(會自動重建)"],
  ["M7 系統", "磁碟可用空間偏低", "一鍵清理快取騰出空間"],
  ["M7 系統", "APFS 本機快照偏多", "一鍵精簡快照"],
  ["M2 損壞", "殘留捷徑 / PATH 設定", "一鍵清理並修正"],
  ["M7 系統", "硬碟 SMART 異常", "提醒備份與送修(硬體,不一鍵)"],
  ["M6 電池", "電池明顯老化", "提醒送修/換電池(硬體,不一鍵)"],
  ["M3 檔案", "大型檔案佔空間", "導引你到明細自行判斷(不一鍵刪)"],
  ["M1 檔案", "重複檔案", "導引你逐組確認(不一鍵刪)"],
  ["M8 背景", "第三方開機自啟過多", "導引你到明細自行停用"],
]));
children.push(new Paragraph({ spacing: { after: 100 } }));
children.push(P("在報告摘要頁底部,可展開「修復涵蓋範圍」看到同樣的對照表,並標出本次掃描實際命中了哪幾項。"));
children.push(IMG(A + "07_coverage.png"));
children.push(CAP("報告內的「修復涵蓋範圍」對照表"));

// ===== 7. 常見問題 =====
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(H1("七、常見問題與注意事項"));
children.push(H2("Q:雙擊後出現「無法打開,因為來自未識別的開發者」?"));
children.push(P("A:按住鍵盤 Control 鍵、用滑鼠點一下「開始體檢.command」,選「打開」,再按一次「打開」。這是 macOS 的安全提示,只需做一次。"));
children.push(H2("Q:提示要安裝「開發者工具」?"));
children.push(P("A:按「安裝」,等 Apple 的安裝視窗完成後,再雙擊一次「開始體檢」即可。這個元件是掃描所需,只需安裝一次。"));
children.push(H2("Q:那個黑色視窗可以關嗎?"));
children.push(P("A:使用中請不要關閉,關掉程式就停止了。完成體檢、處理完修復後,再關閉它即可。"));
children.push(H2("Q:按「修復」按鈕沒反應或失敗?"));
children.push(P("A:修復功能需要透過「開始體檢」自動打開的網頁、且那個黑色視窗仍開著才能運作。常見兩種情況:"));
children.push(B([run("你直接雙擊了 report 資料夾裡的 index.html(網址是 file://…)", { bold: true }), run(":請改從「開始體檢」自動打開的網頁(網址列是 127.0.0.1)操作。")]));
children.push(B([run("你把黑色「開始體檢」視窗關掉了", { bold: true }), run(":請重新雙擊「開始體檢」,再從它打開的網頁操作。")]));
children.push(P("報告偵測到這情況時,會在最上方顯示黃色提示告訴你怎麼做。(純看報告不受影響,只有「修復」需要程式在執行。)"));
children.push(H2("Q:報告是即時的嗎?"));
children.push(P("A:報告反映「這次掃描當下」的狀況。想看最新狀態,回到首頁再按一次「開始體檢」重新掃描即可;修復按鈕也會依新結果自動增減。"));
children.push(H2("Q:我的資料會外傳嗎?"));
children.push(P("A:不會。所有檢查都在你自己的電腦上進行,程式只在本機運作(127.0.0.1),不會把任何資料傳到網路上。"));
children.push(new Paragraph({ spacing: { before: 200 }, alignment: AlignmentType.CENTER,
  children: [new TextRun({ text: "— 祝你的 Mac 常保健康 —", italics: true, color: "777777", size: 20 })] }));

const doc = new Document({
  styles: {
    default: { document: { run: { font: FONT, size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: FONT, color: "0F4C75" },
        paragraph: { spacing: { before: 280, after: 160 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: FONT, color: "1F6390" },
        paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 1 } },
      { id: "Normal", name: "Normal", run: { font: FONT, size: 22 }, paragraph: { spacing: { line: 312 } } },
    ],
  },
  numbering: {
    config: [
      { reference: "b", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 560, hanging: 280 } } } }] },
      { reference: "steps", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "步驟 %1", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 0, hanging: 0 } }, run: { bold: true, color: "0F4C75", size: 24 } } }] },
      { reference: "steps2", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 560, hanging: 280 } } } }] },
    ],
  },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: "MacVitals 使用手冊   ·   ", size: 16, color: "999999" }),
                 new TextRun({ children: [PageNumber.CURRENT], size: 16, color: "999999" })] })] }) },
    children,
  }],
});

Packer.toBuffer(doc).then(buf => { fs.writeFileSync("MacVitals 使用手冊.docx", buf); console.log("OK"); });

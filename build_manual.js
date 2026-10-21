// 重建「MacVitals 使用手冊（白話版）」。內文與結構以 repo 內已提交的 v1.3 .docx 為準(用法見 README「重建手冊」)。
//   node build_manual.js [輸出檔路徑]    預設輸出到目前資料夾的「MacVitals 使用手冊（白話版）.docx」(會覆蓋同名檔)
const fs = require("fs");
const path = require("path");
const { Document, Packer, Paragraph, TextRun, ImageRun,
        AlignmentType, HeadingLevel, LevelFormat, BorderStyle, ShadingType,
        TableOfContents, PageBreak, Footer, PageNumber } = require("docx");

const FONT = "PingFang TC";
const A = path.join(__dirname, "manual_assets");
const OUT = process.argv[2] || "MacVitals 使用手冊（白話版）.docx";
const VERSION = "版本 1.3   ·   2026-06-25"; // 封面版本字串:改版時連同內文一起更新

// ---- helpers ----
const run = (t, o = {}) => new TextRun({ text: t, ...o });
const kids = t => (Array.isArray(t) ? t : [new TextRun(t)]);
const H1 = t => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)] });
const H2 = t => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] });
const P = t => new Paragraph({ spacing: { after: 120 }, children: kids(t) });
const B = t => new Paragraph({ style: "ListParagraph", numbering: { reference: "b", level: 0 }, spacing: { after: 60 }, children: kids(t) });
const STEP = t => new Paragraph({ style: "ListParagraph", numbering: { reference: "steps", level: 0 }, spacing: { before: 120, after: 80 }, children: [run(t, { bold: true })] });
const NUM = t => new Paragraph({ style: "ListParagraph", numbering: { reference: "steps2", level: 0 }, spacing: { after: 60 }, children: kids(t) });
// 重點提示框:左側藍色粗線 + 淡藍底
const NOTE = t => new Paragraph({
  border: { left: { style: BorderStyle.SINGLE, size: 18, color: "0F6FB5" } },
  shading: { type: ShadingType.CLEAR, fill: "EAF2FB" },
  spacing: { before: 80, after: 120 }, children: kids(t) });
const BREAK = () => new Paragraph({ children: [new PageBreak()] });
const CAP = t => new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 220 },
  children: [new TextRun({ text: "▲ " + t, italics: true, size: 18, color: "777777" })] });

function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) }; // PNG IHDR
}
// 截圖置中,寬度 w(px),高度依實際長寬比換算,不壓變形
function IMG(name, w) {
  const file = path.join(A, name);
  if (!fs.existsSync(file)) {
    console.error(`找不到截圖 ${file}\n請先依 README「重建手冊」從已提交的 .docx 取出 4 張截圖到 manual_assets/。`);
    process.exit(1);
  }
  const s = pngSize(file);
  return new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 140, after: 40 },
    children: [new ImageRun({ type: "png", data: fs.readFileSync(file), transformation: { width: w, height: Math.round(w * s.h / s.w) },
      altText: { title: "screenshot", description: "manual screenshot", name: "img" } })] });
}

const children = [];

// ===== 封面 =====
children.push(new Paragraph({ spacing: { before: 1600, after: 0 }, alignment: AlignmentType.CENTER,
  children: [new TextRun({ text: "MacVitals", bold: true, size: 64, color: "0F6FB5" })] }));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 },
  children: [new TextRun({ text: "macOS 健康體檢 — 使用手冊", size: 30, color: "333333" })] }));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 },
  children: [new TextRun({ text: "適用對象:所有人(不需要懂電腦指令)", size: 22, color: "777777" })] }));
children.push(IMG("01_landing.png", 440));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 320 },
  children: [new TextRun({ text: VERSION, size: 20, color: "999999" })] }));
children.push(BREAK());

// ===== 目錄 =====
children.push(H1("目錄"));
children.push(new TableOfContents("目錄", { hyperlink: true, headingStyleRange: "1-3" }));
children.push(BREAK());

// ===== 一、這是什麼? =====
children.push(H1("一、這是什麼?"));
children.push(P("MacVitals 是一個幫你的 Mac 做「健康體檢」的小工具。就像人去做健康檢查一樣,它會一次幫你檢查電腦的十一個面向,告訴你哪裡正常、哪裡需要注意,並對常見的小問題提供「一鍵修復」。"));
children.push(NOTE([run("最重要的一點:", { bold: true }), run("整個檢查過程是「唯讀」的——它只是「看」,不會刪除、搬移或改動你的任何檔案。只有你自己按下修復按鈕、並再次確認之後,它才會處理那一項。")]));

// ===== 二、這給誰用 / 什麼時候用 =====
children.push(H1("二、這給誰用 / 什麼時候用"));
children.push(B("覺得電腦變慢、變燙、變吵,想知道是哪裡出問題時。"));
children.push(B("想定期保養 Mac、清出空間、確認安全設定有沒有開好時。"));
children.push(B("完全不需要懂電腦指令——全程點按滑鼠就能完成。"));

// ===== 三、開始之前 =====
children.push(H1("三、開始之前(需要準備什麼)"));
children.push(B("一台 Mac(macOS)。"));
children.push(B([run("首次使用若提示安裝「開發者工具」", { bold: true }), run(":按「安裝」,完成後再操作一次即可(只需一次)。")]));
children.push(B([run("預留約 5–10 分鐘", { bold: true }), run(":全機掃描需要一點時間,硬碟越大越久。")]));

// ===== 四、怎麼使用(四個步驟) =====
children.push(H1("四、怎麼使用(四個步驟)"));
children.push(STEP("雙擊「開始體檢」"));
children.push(P("在資料夾裡找到「開始體檢.command」,用滑鼠左鍵連點兩下。電腦會打開一個黑色小視窗,並自動開啟瀏覽器。"));
children.push(NOTE([run("小提醒:", { bold: true }), run("若第一次出現「無法打開,因為來自未識別的開發者」,請按住鍵盤 Control 鍵、用滑鼠點一下該檔案,選「打開」,再按一次「打開」(只需一次)。過程中那個黑色視窗請勿關閉,關掉程式就停止了。")]));
children.push(STEP("在網頁上按「開始體檢」"));
children.push(P("瀏覽器會出現下面這個畫面。按下中間藍色的「開始體檢」按鈕。"));
children.push(IMG("01_landing.png", 430));
children.push(CAP("首頁:按「開始體檢」即可開始"));
children.push(STEP("等待掃描完成"));
children.push(P("按下後會出現進度條,並顯示目前正在檢查哪一項(例如「掃描 M3…」)。請耐心等候,通常數分鐘內完成。"));
children.push(IMG("02_progress.png", 430));
children.push(CAP("掃描進行中:進度條顯示目前進度"));
children.push(STEP("自動看報告"));
children.push(P("掃描完成後,網頁會自動跳到一份「體檢報告」。看完、需要的修復也處理完之後,把那個黑色視窗關閉就結束了。"));
children.push(BREAK());

// ===== 五、報告怎麼看 =====
children.push(H1("五、報告怎麼看"));
children.push(P("報告第一頁是「摘要」,把整台電腦的狀況濃縮在這裡:最上面是十一個檢查面向的卡片(點任一張可跳到細節),接著是整體判讀、需要你注意的事(右邊就是修復按鈕)、運作良好的部分,最後可展開「修復涵蓋範圍」對照表。"));
children.push(IMG("03_report_summary.png", 520));
children.push(CAP("報告摘要:十一個面向一覽(此為去敏示範資料)"));
children.push(H2("顏色代表什麼?"));
children.push(B([run("紅色 = 高風險,建議盡快處理", { bold: true, color: "B00020" }), run("(例如防火牆沒開)。")]));
children.push(B([run("黃色 = 中等,建議處理", { bold: true, color: "9A6700" }), run("(例如有套件可更新)。")]));
children.push(B([run("藍色 = 參考,可選優化", { bold: true, color: "1F6390" }), run("(例如可回收的快取)。")]));
children.push(B([run("綠色 = 運作良好,無需處理。", { bold: true, color: "1B7F4B" })]));

// ===== 六、一鍵修復怎麼用 =====
children.push(H1("六、一鍵修復怎麼用"));
children.push(P("在「需要你注意的事」區塊,每一項右邊可能有一顆有顏色的修復按鈕(例如「一鍵清理快取」「更新全域 npm」),以及一顆「查看」按鈕。"));
children.push(IMG("04_attention.png", 510));
children.push(CAP("「需要你注意的事」:右側即修復按鈕(此為去敏示範資料)"));
children.push(NUM("按下你想處理的那一項的修復按鈕。"));
children.push(NUM("會跳出確認視窗說明將要做什麼,確定就按「確定」。"));
children.push(NUM("若該項需要權限(例如開啟防火牆),macOS 會跳出輸入密碼的視窗,輸入你的開機密碼即可。"));
children.push(NUM("畫面右下角會跳出結果訊息(例如釋出了多少空間)。"));
children.push(NOTE([run("安心使用:", { bold: true }), run("修復只會做安全清單內的動作,而且程式會在按下的當下重新確認現況——如果其實沒事可做(例如防火牆其實已經開了),它只會回報「無需變更」,不會亂動。刪重複檔、停用開機程式這類需要你判斷的,以及電池/硬碟這類硬體問題,只會提醒與導引,不會替你動手。")]));

// ===== 七、常見問題 =====
children.push(H1("七、常見問題"));
children.push(H2("Q:那個黑色視窗可以關嗎?"));
children.push(P("A:使用中請不要關閉,關掉程式就停止了。完成體檢、處理完修復後再關閉它即可。"));
children.push(H2("Q:按「修復」按鈕沒反應或失敗?"));
children.push(P("A:修復需要從「開始體檢」自動打開的網頁(網址列是 127.0.0.1)操作,且黑色視窗仍開著。若你直接雙擊了報告檔(網址是 file://…)或關掉了黑色視窗,就會連不上;請重新從「開始體檢」打開的網頁操作。報告偵測到這情況時,會在最上方顯示黃色提示告訴你怎麼做。"));
children.push(H2("Q:我已經有在背景常駐執行,再雙擊「開始體檢」會怎樣?"));
children.push(P("A:不會出錯。程式會發現「已經在執行中」,直接幫你打開報告網頁,不會重複啟動,也不會卡住。"));
children.push(H2("Q:報告是即時的嗎?"));
children.push(P("A:報告反映「這次掃描當下」的狀況。想看最新狀態,回首頁再按一次「開始體檢」重新掃描即可。"));

// ===== 八、安全與隱私 =====
children.push(H1("八、安全與隱私"));
children.push(B("所有檢查都在你自己的電腦上進行,程式只在本機運作(127.0.0.1),不會把任何資料傳到網路上。"));
children.push(B("掃描階段全程唯讀;所有修復都需你親自點擊並確認,且執行當下會再次確認現況。"));
children.push(P([run("— 祝你的 Mac 常保健康 —", { italics: true })]));

const doc = new Document({
  styles: {
    default: { document: { run: { font: FONT, size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: FONT, color: "0F6FB5" },
        paragraph: { spacing: { before: 280, after: 160 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: FONT, color: "1F6390" },
        paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 23, bold: true, font: FONT, color: "1F6390" },
        paragraph: { spacing: { before: 160, after: 80 }, outlineLevel: 2 } },
      { id: "Normal", name: "Normal", run: { font: FONT, size: 22 }, paragraph: { spacing: { line: 312 } } },
    ],
  },
  numbering: {
    config: [
      { reference: "b", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 560, hanging: 280 } } } }] },
      { reference: "steps", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "步驟 %1", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 0, hanging: 0 } }, run: { bold: true, color: "0F6FB5", size: 24 } } }] },
      { reference: "steps2", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 560, hanging: 280 } } } }] },
    ],
  },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: "MacVitals   ·   ", size: 16, color: "999999" }),
                 new TextRun({ children: [PageNumber.CURRENT], size: 16, color: "999999" })] })] }) },
    children,
  }],
});

Packer.toBuffer(doc).then(buf => { fs.writeFileSync(OUT, buf); console.log("OK → " + OUT); });

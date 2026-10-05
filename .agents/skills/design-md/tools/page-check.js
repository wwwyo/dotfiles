/**
 * ブラウザで開いた生成ページの構図を計測する読み取り専用スクリプト。
 *
 * headless Chrome がこの環境で動かないため、計測だけをブラウザ内 JS に分離し、
 * page-check.py が静的ルールと合わせて判定する。副作用は一切持たない。
 *
 * 使い方: 対象ページを開いた状態でこの全文をコンソール / javascript_tool /
 * agent-browser eval --stdin に貼り、最終式（JSON.stringify(result)）の返り値を
 * そのままファイルへ保存して page-check.py --layout に渡す。
 */
(function () {
  /**
   * 要素を人間が特定できる程度の短いセレクタ文字列にする（一意性は保証しない）。
   *
   * 祖先2階層までの tag/class ヒントを前置し、目視での探索を助ける。
   */
  function describe(el) {
    function part(node) {
      if (!node || node.nodeType !== 1) return "";
      var tag = node.tagName.toLowerCase();
      var id = node.id ? "#" + node.id : "";
      var cls = node.classList && node.classList.length ? "." + node.classList[0] : "";
      return tag + id + cls;
    }
    var chain = [];
    var node = el;
    for (var i = 0; i < 3 && node; i++) {
      chain.unshift(part(node));
      node = node.parentElement;
    }
    return chain.filter(Boolean).join(" > ");
  }

  /**
   * ratio 計算の 0 除算を避けるためのガード付き除算。
   */
  function safeRatio(numerator, denominator) {
    if (!denominator || denominator <= 0) return 0;
    return numerator / denominator;
  }

  var blocks = [];
  var blockSelectors = ["table", ".stat-strip", ".card", "section", "main > *", "body > *"];
  var seen = new Set();
  blockSelectors.forEach(function (sel) {
    document.querySelectorAll(sel).forEach(function (el) {
      if (seen.has(el)) return;
      seen.add(el);
      var rect = el.getBoundingClientRect();
      var parent = el.parentElement;
      var containerWidth = parent ? parent.getBoundingClientRect().width : 0;
      blocks.push({
        selector: describe(el),
        width: rect.width,
        containerWidth: containerWidth,
        ratio: safeRatio(rect.width, containerWidth),
      });
    });
  });

  var stripItems = [];
  document.querySelectorAll(".stat-strip").forEach(function (strip) {
    var stripWidth = strip.getBoundingClientRect().width;
    var childrenWidthSum = 0;
    Array.prototype.forEach.call(strip.children, function (child) {
      childrenWidthSum += child.getBoundingClientRect().width;
    });
    stripItems.push({
      selector: describe(strip),
      stripWidth: stripWidth,
      childrenWidthSum: childrenWidthSum,
      ratio: safeRatio(childrenWidthSum, stripWidth),
    });
  });

  var negatives = [];
  document.querySelectorAll(".negative").forEach(function (el) {
    negatives.push({
      selector: describe(el),
      text: (el.textContent || "").trim(),
    });
  });

  var result = {
    blocks: blocks,
    stripItems: stripItems,
    viewport: { width: window.innerWidth, height: window.innerHeight },
    negatives: negatives,
  };

  return JSON.stringify(result);
})();

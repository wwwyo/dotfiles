(async () => {
  const results = [];
  for (const width of [320, 375, 414, 768]) {
    const frame = document.createElement('iframe');
    frame.style.cssText = `width:${width}px;height:1600px;border:0;position:fixed;left:0;top:0;z-index:99999`;
    frame.src = location.href;
    try {
      await new Promise((resolve, reject) => {
        frame.onload = resolve;
        frame.onerror = reject;
        document.body.append(frame);
      });
      const doc = frame.contentDocument;
      await doc.fonts.ready;
      const buttons = Array.from(doc.querySelectorAll('button')).map(button => {
        const rect = button.getBoundingClientRect();
        const labels = Array.from(button.querySelectorAll('[class*="label"], [class*="copy"]'))
          .filter(label => label.children.length === 0 && label.getBoundingClientRect().width > 0);
        return {
          text: button.innerText.trim(), height: rect.height, left: rect.left, right: rect.right,
          labels: labels.map(label => {
            const range = doc.createRange();
            range.selectNodeContents(label);
            const lines = new Set(Array.from(range.getClientRects()).filter(r => r.width > 0).map(r => Math.round(r.top)));
            return { text: label.innerText, lines: lines.size };
          })
        };
      });
      results.push({ width, innerWidth: frame.contentWindow.innerWidth,
        scrollWidth: doc.documentElement.scrollWidth, buttons });
    } finally {
      frame.remove();
    }
  }
  return results;
})()

/**
 * ページ内の要素に赤枠・矢印の注釈を描画する。座標をエージェントが目視推定する代わりに、
 * CSS selector / テキストで対象を指定させる。呼び出し方は tools/anno-example.md を参照。
 *
 * spec の形:
 *   { type: "box", sel, txt?, up?, pad?, label?, labelPos?: "above"|"right"|"below" }
 *   { type: "arrow", sel, txt?, toSel, toTxt?, label?, fromX?, toX?, toY? }
 *
 * - sel: 対象を探す CSS selector。txt を指定すると `el.textContent.trim().startsWith(txt)` で絞る
 * - up: 見つけた要素から親へ何階層遡るか（クリック領域とハイライトしたい枠が違うときに使う）
 * - pad: 枠の余白（px）。省略時 6
 * - label: 枠/矢印に添えるラベル文字列。省略すると付けない
 * - labelPos: box のラベル位置。"above"（既定）/ "right" / "below"
 * - arrow は toSel/toTxt で終点要素を指定し、始点要素から終点要素へ曲線矢印を引く
 *
 * opts（第2引数、省略可）:
 *   { full?: boolean, number?: boolean }
 * - full: true なら full-page screenshot 向けに絶対配置 + スクロール量オフセットで描画する。
 *   省略時（既定）は viewport 固定
 * - number: true なら描画できた spec の登場順に ①②… を label の先頭へ自動で振る
 *   （MISSING になった spec はカウントしない）
 *
 * 戻り値: "box セレクタ, arrow セレクタ, MISSING セレクタ" 形式のサマリ文字列。
 * MISSING は要素（box の対象、または arrow の始点/終点）が見つからず描画できなかった spec を示す。
 * 呼び出し側は戻り値を見て指定した注釈が全部描けたか必ず確認すること。
 */
(specs, opts = {}) => {
  const R = '#de0836';
  const CIRCLED = ['①','②','③','④','⑤','⑥','⑦','⑧','⑨','⑩','⑪','⑫','⑬','⑭','⑮'];
  const full = !!opts.full;
  document.getElementById('anno')?.remove();
  const root = document.createElement('div'); root.id = 'anno';
  root.style.cssText = full
    ? 'position:absolute;top:0;left:0;width:100%;height:'+document.documentElement.scrollHeight+'px;pointer-events:none;z-index:99999;font-family:"Hiragino Sans","Noto Sans JP",sans-serif'
    : 'position:fixed;inset:0;pointer-events:none;z-index:99999;font-family:"Hiragino Sans","Noto Sans JP",sans-serif';
  const svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
  svg.setAttribute('style','position:absolute;inset:0;width:100%;height:100%;overflow:visible');
  svg.innerHTML = '<defs><marker id="ah" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="'+R+'"/></marker></defs>';
  root.appendChild(svg);
  const find = (sel, txt) => { const els=[...document.querySelectorAll(sel)]; return txt ? els.find(e=>e.textContent.trim().startsWith(txt)) : els[0]; };
  const rectOf = (el) => { const r = el.getBoundingClientRect(); if (!full) return r; const ox = window.scrollX, oy = window.scrollY; return { left: r.left+ox, top: r.top+oy, right: r.right+ox, bottom: r.bottom+oy, width: r.width, height: r.height }; };
  const label = (x, y, text) => { const d=document.createElement('div'); d.textContent=text; d.style.cssText='position:absolute;left:'+x+'px;top:'+y+'px;background:'+R+';color:#fff;font-size:14px;font-weight:700;padding:3px 8px;border-radius:3px;white-space:nowrap;line-height:1.4'; root.appendChild(d); };
  const box = (r, text, pad=6, pos) => { const d=document.createElement('div'); d.style.cssText='position:absolute;left:'+(r.left-pad)+'px;top:'+(r.top-pad)+'px;width:'+(r.width+pad*2)+'px;height:'+(r.height+pad*2)+'px;border:3px solid '+R+';border-radius:6px;box-sizing:border-box'; root.appendChild(d); if(text) { if (pos==='right') label(r.right+pad+10, r.top+r.height/2-13, text); else if (pos==='below') label(r.left-pad, r.bottom+pad+6, text); else label(r.left-pad, Math.max(4, r.top-pad-30), text); } };
  const out = [];
  let n = 0;
  for (const s of specs) {
    let el = find(s.sel, s.txt); if(!el){ out.push('MISSING '+(s.txt||s.sel)); continue; }
    for (let k=0;k<(s.up||0);k++) el = el.parentElement;
    const r = rectOf(el);
    if (s.type==='box') {
      n++;
      const mark = opts.number ? (CIRCLED[n-1] || (n+'.')) + ' ' : '';
      box(r, s.label ? mark+s.label : (opts.number ? mark.trim() : undefined), s.pad, s.labelPos); out.push('box '+(s.txt||s.sel));
    }
    if (s.type==='arrow') {
      const to = find(s.toSel, s.toTxt); if(!to){ out.push('MISSING '+(s.toTxt||s.toSel)); continue; }
      n++;
      const mark = opts.number ? (CIRCLED[n-1] || (n+'.')) + ' ' : '';
      const t=rectOf(to);
      const x1=r.left+ (s.fromX ?? 40), y1=r.top+r.height/2, x2=t.left+(s.toX ?? 40), y2=t.top+(s.toY ?? t.height/2);
      const p=document.createElementNS('http://www.w3.org/2000/svg','path'); const cx = Math.min(x1,x2)-60; p.setAttribute('d',`M${x1},${y1} C${cx},${y1} ${cx},${y2} ${x2},${y2}`); p.setAttribute('stroke',R); p.setAttribute('stroke-width','3'); p.setAttribute('fill','none'); p.setAttribute('marker-end','url(#ah)'); svg.appendChild(p);
      box(r, null, 4); if (s.label || opts.number) label(cx-10, (y1+y2)/2-12, s.label ? mark+s.label : mark.trim()); out.push('arrow '+(s.txt||s.sel)); }
  }
  document.body.appendChild(root); return out.join(', ');
}

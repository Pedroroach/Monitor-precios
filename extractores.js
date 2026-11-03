// Lectores (extractores) que corren DENTRO de la página de cada cadena. Los inyecta scraper.py.
// No filtran nada: devuelven todo lo que trae cada búsqueda. El filtro está en process.py,
// así se puede ver qué se descartó y por qué.
//
// Cada producto se devuelve como:
// {busqueda, nombre, marca, precio, precio_normal, ppk, ppk_normal, precio_tarjeta, promo,
//  kg_unidad, formato, unidad, url, stock, categoria_web, ppu, ppu_normal, ppu_unidad}
// ppk = precio por kilo que publica la cadena. ppu = precio por unidad de medida que publica la cadena
// en cualquier unidad (kg, litro, unidad), con ppu_unidad diciendo cuál.
(() => {
  const MV = {};
  MV.num = s => s ? Number(String(s).replace(/[^0-9]/g, '')) || null : null;
  const fila = (q, r) => ({
    busqueda: q, nombre: r.name, marca: r.brand || '', precio: r.price ?? null, precio_normal: r.list ?? null,
    ppk: r.ppk ?? null, ppk_normal: r.ppkList ?? null, precio_tarjeta: r.card ?? null, promo: r.promo || '',
    kg_unidad: r.kgUn ?? null, formato: r.size || '', unidad: r.unit || '', url: r.url || '',
    stock: r.stock === false ? 0 : 1, categoria_web: r.cat || '',
    ppu: r.ppu ?? null, ppu_normal: r.ppuList ?? null, ppu_unidad: r.ppuUnit || ''});

  // ---------- JUMBO ----------
  const grab = (s,start) => { let d=0,inS=false,esc=false; for (let k=start;k<s.length;k++){ const c=s[k]; if(inS){ if(esc)esc=false; else if(c==='\\')esc=true; else if(c==='"')inS=false; continue;} if(c==='"')inS=true; else if(c==='{')d++; else if(c==='}'){ d--; if(d===0) return s.slice(start,k+1);} } return null; };
  // Jumbo (y Santa Isabel desde nov-2026) dibujan la página con Next.js: los productos vienen en self.__next_f
  MV.nextProductos = (h) => {
    const s = [...h.matchAll(/self\.__next_f\.push\(\[1,"(.*?)"\]\)<\/script>/gs)].map(m=>{try{return JSON.parse('"'+m[1]+'"')}catch(e){return ''}}).join('');
    const catMap = {}; for (const m of s.matchAll(/"href":"(\/[^"]+\/p)"[^}]*?"data-gtm-product-click":"((?:\\.|[^"\\])*)"/g)) { try{ catMap[m[1]] = JSON.parse(JSON.parse('"'+m[2]+'"')).category }catch(e){} }
    const out=[]; const seen=new Set(); let idx=0;
    while ((idx = s.indexOf('"product":{"productId"', idx)) >= 0) { const js = grab(s, idx+10); idx += 10; if (!js) continue; let p; try{ p=JSON.parse(js) }catch(e){ continue }
      if (seen.has(p.productId)) continue; seen.add(p.productId); const it = p.items?.[0]; if (!it) continue;
      const promos = (it.promotions||[]).filter(x=>x.mQuantity>1||x.unitPrice<it.price).map(x=>x.mQuantity>1?`${x.mQuantity} x $${Math.round(x.unitPrice*x.mQuantity)}`:`$${x.unitPrice}`);
      const url = '/'+p.slug+'/p';
      out.push({name:it.name, brand:p.brand, price:it.price, list:it.listPrice, ppk:it.ppumMeasurementUnit==='kg'?it.ppumPrice:null, ppkList:it.ppumMeasurementUnit==='kg'?it.ppumListPrice:null, unit:it.measurementUnit, kgUn:it.measurementUnitUn==='kg'?it.unitMultiplierUn:null, ppu:it.ppumPrice, ppuList:it.ppumListPrice, ppuUnit:it.ppumMeasurementUnit, stock:it.stock, promo:promos.join(' | '), url, cat:catMap[url]||''}); }
    return out; };
  MV.jumboQ = async (q, page=1) => MV.nextProductos(await (await fetch('/busqueda?ft='+encodeURIComponent(q)+'&page='+page)).text());

  // ---------- SANTA ISABEL ----------
  MV.santaisabelQ = async (q, page=1) => {
    const h = await (await fetch('/busqueda?ft='+encodeURIComponent(q)+'&page='+page)).text();
    const m = h.match(/__renderData = (".*?");/s); if (!m) return MV.nextProductos(h);  // sitio nuevo (igual a Jumbo)
    const d = JSON.parse(JSON.parse(m[1])); const prods = d.plp?.plp_products?.products || [];
    return prods.map(p => { const it=p.items[0]; const o=it.sellers[0].commertialOffer;
      let pd={}; try{ const g=p.specificationGroups.find(g=>g.name==='Configuraciones'); pd=JSON.parse(g.specifications.find(s=>s.name==='ProductData').values[0]); }catch(e){}
      const byKg = it.measurementUnit==='kg'; const kg = byKg ? it.unitMultiplier : (pd.measurement_unit_un==='kg' ? pd.unit_multiplier_un : null);
      return {name:p.productName, brand:p.brand, price: byKg?Math.round(o.Price*kg):o.Price, list: byKg?Math.round(o.ListPrice*kg):o.ListPrice,
        ppk: byKg?o.Price:(kg?Math.round(o.Price/kg):null), ppkList: byKg?o.ListPrice:(kg?Math.round(o.ListPrice/kg):null),
        kgUn:kg, unit:byKg?'kg':'un', stock:o.AvailableQuantity>0, url:'/'+p.linkText+'/p', cat:(p.categories||[])[0]||''}; }); };

  // ---------- UNIMARC ----------
  MV.unimarcQ = async (q) => {
    const r = await fetch('https://bff-unimarc-ecommerce.unimarc.cl/catalog/product/search',{method:'POST',headers:{'content-type':'application/json','channel':'UNIMARC','source':'web','version':'1.0.0'},body:JSON.stringify({from:'0',orderBy:'',searching:q,promotionsOnly:false,to:'79',userTriggered:true})});
    const j = await r.json(); const kgp = s => /x kg/i.test(s||'') ? MV.num(s) : null;
    const pu = s => { const m = /x\s*(kg|lts?|litros?|l|un|unidad(?:es)?)\s*$/i.exec(s||''); return m ? {v: MV.num(s.slice(0, m.index)), u: m[1]} : {v: null, u: ''}; };
    return (j.availableProducts||[]).map(p => { const pr=p.price, it=p.item, pd=p.priceDetail||{};
      let promo=''; if (pd.promotionType==='mx$' && pd.discountPrice) promo=String(pd.discountPrice).replace(/\s+/g,' '); else if (pd.discountPercentage) promo='-'+String(pd.discountPercentage).replace('%','')+'%';
      const isMx = pd.promotionType==='mx$';
      return {name:it.nameComplete||it.name, brand:it.brand, price: isMx?MV.num(pr.price):(MV.num(pd.discountPrice)||MV.num(pr.price)), list:MV.num(pd.listPrice)||MV.num(pr.listPrice),
        ppk: isMx?kgp(pr.ppum):(MV.num(pd.discountPpumPrice)||kgp(pr.ppum)), ppkList:kgp(pd.ppumListPrice)||kgp(pr.ppumListPrice),
        ppu: isMx?pu(pr.ppum).v:(MV.num(pd.discountPpumPrice)||pu(pr.ppum).v), ppuList:(pu(pd.ppumListPrice).v||pu(pr.ppumListPrice).v), ppuUnit:pu(pr.ppum).u||pu(pd.ppumListPrice).u, promo, size:it.netContent, unit:it.measurementUnit,
        stock:pr.availableQuantity>0, url:it.slug, cat:(it.categories||[])[0]||''}; }); };

  // ---------- TOTTUS ----------
  MV.tottusQ = async (q) => {
    const h = await (await fetch('/tottus-cl/buscar?Ntt='+encodeURIComponent(q))).text();
    const m = h.match(/<script id="__NEXT_DATA__"[^>]*>(.*?)<\/script>/s); if (!m) return [];
    const d = JSON.parse(m[1]);
    return (d.props.pageProps.results||[]).map(p => { const P={}; for (const x of p.prices||[]) P[x.type]={v:MV.num(x.price[0]), pum:x.pum?{u:x.pum.label,v:MV.num(x.pum.price[0])}:null};
      const cur=P.internetPrice||P.eventPrice||P.normalPrice, nor=P.normalPrice||cur, card=P.cmrPrice; const ppkOf=o=>o&&o.pum&&o.pum.u==='KG'?o.pum.v:null;
      return {name:p.displayName, brand:p.brand, price:cur?.v, list:nor?.v, ppk:ppkOf(cur), ppkList:ppkOf(nor), card:card?.v||null, promo:p.discountBadge?.label||'', size:p.measurements?.format, unit:p.measurements?.unit, url:p.url, cat:p.merchantCategoryId}; }); };

  // Forma "pedir": una función que recorre todas las búsquedas desde el sitio ya abierto.
  // Las cadenas que paginan (Jumbo, Santa Isabel) traen 40 por página: si una página trae menos, no hay más.
  const PAGINADAS = {jumbo: MV.jumboQ, santaisabel: MV.santaisabelQ};
  const UNA_PAGINA = {unimarc: MV.unimarcQ, tottus: MV.tottusQ};
  MV.leer = async (cadena, busquedas, maxPaginas) => {
    const out = [], errores = [];
    for (const q of busquedas) {
      try {
        if (PAGINADAS[cadena]) {
          for (let pg = 1; pg <= maxPaginas; pg++) { const r = await PAGINADAS[cadena](q, pg); out.push(...r.map(x => fila(q, x))); if (r.length < 40) break; }
        } else if (UNA_PAGINA[cadena]) {
          out.push(...(await UNA_PAGINA[cadena](q)).map(x => fila(q, x)));
        } else { throw new Error('no hay lector para ' + cadena); }
      } catch (e) { errores.push(q + ': ' + e.message); }
    }
    return {filas: out, errores};
  };

  // ---------- LÍDER (forma "navegar": scraper.py abre cada búsqueda y llama a esto) ----------
  MV.liderPage = (q) => { const nd = document.getElementById('__NEXT_DATA__'); if (!nd) return {error: document.title};
    const sr = JSON.parse(nd.textContent).props.pageProps.initialData.searchResult;
    const items = (sr.itemStacks||[]).flatMap(s=>s.items||[]).filter(x=>x.__typename==='Product').map(p => { const pi=p.priceInfo||{};
      return fila(q, {name:p.name, brand:p.brand, price:p.price||MV.num(pi.linePrice), list:MV.num(pi.wasPrice), promo:p.flag||p.badge?.text||'', stock:!p.isOutOfStock,
        url:'https://super.lider.cl'+p.canonicalUrl, cat:(p.category?.path||[]).map(x=>x.name).join('/')}); });
    return {total: sr.aggregatedCount ?? sr.count ?? null, items}; };

  // Diagnóstico: cuando una cadena no trae nada, mirar qué respondió el sitio (no intenta saltarse nada).
  MV.diag = async (url) => { try { const r = await fetch(url); const h = await r.text();
    const t = (h.match(/<title[^>]*>([^<]*)/i)||[])[1]||'';
    return {status: r.status, largo: h.length, titulo: t.trim().slice(0,80), renderData: h.includes('__renderData'), nextData: h.includes('__NEXT_DATA__'), next_f: h.includes('self.__next_f')}; }
    catch (e) { return {error: e.message}; } };

  window.MV = MV;
})();

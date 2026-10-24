# 星牧智控 · 单文件官网提示词（可整段交给实现 AI）

> 用法：从下面「目标」开始直到文末，整段复制给实现 AI（或前端同事）。
> 它产出的是一个可直接双击打开的 `index.html`：四个视图、真实可用的页面切换、完整动效。
> 原版 Petalyx 提示词的信息架构与动效语言被保留，品牌、内容、素材与页面结构换成「星牧智控」。
>
> 本文件基于仓库事实撰写（见 `README.md`、`HANDOFF.md`、`web/src/`）。所有文案口径必须遵守第 2 节的禁令。

---

## 目标

做一个名为 **星牧智控** 的产品官网页面：把牧场视频变成可追溯的行为与健康风险证据。视觉主题是「**晨雾牧场 · 水彩科技感**」——清晨的白雾与橄榄绿草坡、半透明玻璃仪表、夜间星空湖面；不是樱花粉，也不是通用 SaaS 蓝紫。

**这是一个多视图单文件站点**：首页 / 能力 / 数据与边界 / 关于，四个页面全部真实存在、可互切、可分享、可刷新、可后退。原提示词里的「滚动章节」不再是唯一交互，导航切换必须真的换页面（详见第 5 节）。

---

## 1. 硬性约束（违反任一条即不合格）

1. 只产出一个 `index.html`，内联 `<style>` 与 `<script>`，无构建步骤、无框架、无 npm。
2. **零外部图片、零外部视频、零图标字体**。所有插画、图标、星点、云、牛群都用内联 SVG 或 CSS 渐变绘制。唯一允许的网络请求：
   - Google Fonts（Inter Tight + Noto Sans SC，见第 4 节）
   - 三个 CDN 脚本：GSAP 3.12.5、ScrollTrigger 3.12.5、Lenis 1.1.13
   - 内联 `data:image/svg+xml` favicon
3. 四个视图必须同时存在于 DOM，切换由 hash 路由驱动：`#/home`、`#/capabilities`、`#/evidence`、`#/about`。**禁止用纯锚点滚动冒充页面切换。**
4. 所有交互真实可用：导航、三面板手风琴、计数器、表单校验、页脚 logo 动画、页内链接、返回顶部。**禁止 mock 按钮、禁止 `href="#"` 死链、禁止 TODO。**
5. 360px 起无横向滚动条（`body{overflow-x:hidden}` + `#app{overflow:clip}`）。
6. 断网（CDN 全部失败）时：正文可见、四个视图仍可点击切换、手风琴与表单仍可用。动效全部降级、不得白屏。
7. `prefers-reduced-motion: reduce` 下：关闭无限动画与入场缩放，内容直接可见。
8. 文案不得越界，见第 2 节；数字必须标明「开发样例」。

---

## 2. 品牌与口径

- **名称**：星牧智控（英文副标 `AGRINEBULA`，小号、字距 `.18em`、全大写）。
- **一句话**：从一段牧场视频，到一份可核查的行为与健康风险证据。
- **受众**：牧场场长、技术员、大创评审、合作牧场；首次接触、需要 30 秒内判断「这东西能干什么、不能干什么」。
- **语气**：克制、具体、可核查。多动词，少形容词；句子短，允许口语但不要营销腔。
- **绝不出现**：客户 Logo 墙、伪造的客户证言、五星好评、「已服务 N 家牧场」、准确率 99%。

### 口径对照（必须遵守）

| ❌ 不能写 | ✅ 应写成 |
| --- | --- |
| 疾病预测、疾病诊断、发病时间 | 健康风险辅助筛查、核查线索 |
| AI 替兽医看病 | 规则型提示，结论由人工复核确认 |
| 自动存栏、存栏真值 | 存栏核对参考、差额提醒（需人工复点） |
| 跨视频识别同一头牛 | 视频内 Track ID（仅本段视频有效） |
| 100% 准确、零误报 | 给出证据与不确定片段 |
| 已上线牧场生产、真实客户 | 大学生创新创业训练计划项目、科研原型 |

允许引用的仓库事实（可用在页面上，注明「开发样例」）：
- 检测：YOLO11 牛只检测；跟踪：ByteTrack；行为四类：采食、饮水、站立反刍、卧姿休息。
- 规则型风险提示：静止、离群、活动量下降；每条提示带秒数、截图与前后片段。
- 开发样例视频：210 帧、26 个视频内 Track ID、26 条规则提示。
- 圈舍存栏核对：登记数 / 清点数 / 拍摄覆盖分栏；差额先进「待复点」。
- 外部样本：ICAERUS 羊视频用于暴露域差异；公开数据结果不代表新牧场泛化。

---

## 3. 设计语言

- **明暗双场景**：首页 / 能力 / 关于 = 晨雾白绿；数据与边界 = 星夜深蓝（`#0a1424`）。页脚统一 lime。
- **形状**：药丸导航、票券缺口卡片、细线网格方格、磨砂玻璃方块；大圆角 22px，按钮全圆。
- **水彩感**：低对比、柔和边缘、半透明层叠、轻微噪点；不要重投影、不要霓虹描边。
- **东方排版**：标题收紧字距（`-.02em` 起），中文**不用假斜体**；数字统一 `font-variant-numeric: tabular-nums`。
- **插画风格**：扁平剪影 + 叠色（橄榄、苔绿、嫩黄），边缘用 `filter: blur(1px)` 制造水彩晕；牛用侧面剪影，不画细节。

### 设计变量

```css
:root{
  --ink:#121410; --olive:#4d6a10; --green:#6f9a0c; --lime:#b4cd52;
  --pill:#e7efcf; --line:#eef0ea; --bg:#fff; --radius:22px;
  --mist:#f3f7ea; --sky:#dceac2; --sun:#f5e3ad;
  --night:#0a1424; --night-2:#123245; --star:#f4e7c3;
  --soft:0 18px 40px rgba(40,60,10,.08);
}
```

---

## 4. 文档头、字体与全局样式

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>星牧智控 — 让每一段牧场视频都变成可追溯的证据</title>
  <meta name="description" content="把牧场视频变成可追溯的行为与健康风险证据：牛只识别、行为分析、人工复核与圈舍核对，一个科研原型。" />
  <link rel="icon" href="data:image/svg+xml,..." />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter+Tight:ital,wght@0,400;0,500;0,600;0,700;1,400;1,500&family=Noto+Sans+SC:wght@400;500;700&display=swap" rel="stylesheet" />
  <style>/* 全部样式 */</style>
</head>
<body class="intro">
  <div class="backdrop" aria-hidden="true"></div>
  <div id="app">
    <header class="nav" id="siteNav">…</header>
    <main id="views">
      <section class="view" id="view-home" data-view="home">…</section>
      <section class="view" id="view-capabilities" data-view="capabilities">…</section>
      <section class="view" id="view-evidence" data-view="evidence">…</section>
      <section class="view" id="view-about" data-view="about">…</section>
    </main>
    <footer id="footer">…</footer>
  </div>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/ScrollTrigger.min.js"></script>
  <script src="https://unpkg.com/lenis@1.1.13/dist/lenis.min.js"></script>
  <script>/* 全部逻辑，单 IIFE */</script>
</body>
</html>
```

全局基础样式（照抄，不要换字体栈）：

```css
*{box-sizing:border-box;margin:0;padding:0}
html{background:#e9eee0}
html.lenis,html.lenis body{height:auto}
.lenis.lenis-smooth{scroll-behavior:auto!important}
body{font-family:"Inter Tight","Noto Sans SC","PingFang SC","Microsoft YaHei",system-ui,sans-serif;
  color:var(--ink);background:transparent;overflow-x:hidden;-webkit-font-smoothing:antialiased}
img,svg{display:block;max-width:100%}
a{color:inherit;text-decoration:none}
button{font:inherit;color:inherit;background:none;border:0;cursor:pointer}
::selection{background:var(--lime);color:#1b2410}
:focus-visible{outline:2px solid var(--green);outline-offset:3px;border-radius:10px}
.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
```

共享组件：

```css
.pill{display:inline-flex;align-items:center;gap:6px;font-size:11px;font-weight:500;
  padding:5px 10px;border-radius:999px;background:var(--pill);color:#2c3a10;letter-spacing:.01em}
.h2{font-size:clamp(26px,3.1vw,44px);font-weight:400;letter-spacing:-.03em;line-height:1.18;text-align:center}
.btn{display:inline-flex;align-items:center;justify-content:center;height:36px;padding:0 16px;border-radius:999px;
  background:var(--olive);color:#f3f8e4;font-size:13px;font-weight:600;letter-spacing:-.01em;white-space:nowrap;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.25),0 2px 6px rgba(60,80,10,.25);
  transition:transform .3s,background .3s}
.btn:hover{transform:translateY(-1px);background:#5a7c14}
.btn-ghost{background:rgba(255,255,255,.7);color:#2b3a10;border:1px solid #d8e3bd;box-shadow:none}
.btn-ghost:hover{background:#fff}
.w{display:inline-block;will-change:transform,filter,opacity}
.glass{position:absolute;border-radius:12px;background:rgba(255,255,255,.16);
  border:1px solid rgba(255,255,255,.55);
  -webkit-backdrop-filter:blur(10px) saturate(1.2);backdrop-filter:blur(10px) saturate(1.2);
  box-shadow:inset 0 1px 0 rgba(255,255,255,.4)}
.grid-sq{position:absolute;border:1px solid #edf0e8;border-radius:10px;pointer-events:none}
@keyframes driftA{to{transform:translateX(26px) translateY(4px)}}
@keyframes driftB{to{transform:translateX(-30px) translateY(6px)}}
.drift-a{animation:driftA 14s ease-in-out infinite alternate}
.drift-b{animation:driftB 17s ease-in-out infinite alternate}
@keyframes twinkle{0%,100%{opacity:.9;transform:scale(1)}50%{opacity:.25;transform:scale(.72)}}
@keyframes fall{to{transform:translate(var(--dx),110vh) rotate(540deg)}}
```

关键帧 `fall` 只给 CTA 的萤火光点用（页脚无花瓣，原版粉色花瓣全部删掉）。

---

## 5. 骨架与路由（「切换页面」完整规格）

### 5.1 外壳

```css
.backdrop{position:fixed;inset:-40px;z-index:0;transform:scale(1.3);filter:blur(18px) saturate(1.1);
  background:
    radial-gradient(60% 45% at 72% 16%,#fff9e6 0%,rgba(255,249,230,0) 60%),
    radial-gradient(55% 40% at 18% 26%,#eaf3d3 0%,rgba(234,243,211,0) 70%),
    linear-gradient(#f8fbf0 0%,#e2eec8 48%,#a9c56c 100%)}
#app{position:relative;z-index:1;background:#fff;transform-origin:50% 50vh;overflow:clip}
body.intro #app{transform:scale(.9);border-radius:28px}
```

- 开场：白页面从 90% 缩放、圆角 28px，浮在模糊的牧场色块上，1.4s 展开；`onComplete` 移除 `body.intro`，`#app` 清空 transform，`.backdrop` 删除。
- 四个视图里，`home` 与 `capabilities`、`about` 白底；`evidence` 允许整页星夜底色（`background:var(--night)`）。

### 5.2 顶部药丸导航（固定）

```html
<header class="nav" id="siteNav">
  <a class="brand" href="#/home" data-route="home" aria-label="星牧智控首页">
    <svg viewBox="0 0 30 22" aria-hidden="true">
      <circle cx="4" cy="17" r="3.6" fill="currentColor"/>
      <path d="M10.5 18.5 16.8 5.2 25.5 18.5" fill="none" stroke="currentColor"
            stroke-width="5.4" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
    <span class="brand-cn">星牧智控</span>
  </a>
  <nav class="nav-links" aria-label="主导航">
    <a href="#/home" data-route="home">首页</a>
    <a href="#/capabilities" data-route="capabilities">能力</a>
    <a href="#/evidence" data-route="evidence">数据与边界</a>
    <a href="#/about" data-route="about">关于</a>
  </nav>
  <a class="btn nav-cta" href="#/home" data-route="home" data-anchor="#cta">预约演示</a>
</header>
```

```css
.nav{position:fixed;top:22px;left:50%;transform:translateX(-50%);z-index:60;
  display:flex;align-items:center;gap:38px;padding:5px 5px 5px 16px;border-radius:999px;
  background:rgba(255,255,255,.9);box-shadow:0 0 0 1px rgba(0,0,0,.05),0 6px 18px rgba(0,0,0,.06);
  -webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px)}
.brand{display:flex;align-items:center;gap:7px;font-size:20px;font-weight:500;letter-spacing:-.03em}
.brand svg{width:26px;height:19px}
.nav-links{display:flex;align-items:center;gap:2px;font-size:13px;font-weight:500;color:#2b3026}
.nav-links a{padding:7px 12px;border-radius:999px;transition:background .25s,color .25s}
.nav-links a:hover{background:rgba(231,239,207,.65)}
.nav-links a[aria-current="page"]{background:var(--pill);color:#2c3a10}
@media (max-width:760px){
  .nav{top:14px;gap:10px;padding:4px 4px 4px 12px;max-width:calc(100% - 16px)}
  .brand{font-size:17px}.brand svg{width:22px;height:16px}
  .nav-links{font-size:12px;gap:0}.nav-links a{padding:6px 8px}
  .nav-cta{display:none}
}
@media (max-width:380px){
  .brand{font-size:15px}.brand svg{width:20px;height:14px}
  .nav-links a{padding:6px 6px;font-size:11.5px}
}
```

- 当前页高亮用 `aria-current="page"`（JS 维护）。
- 导航不隐藏在滚动里，始终保持可达。

### 5.3 路由表

| key | hash | 页面标题（document.title） | 背景 |
| --- | --- | --- | --- |
| `home` | `#/home` | 星牧智控 — 让每一段牧场视频都变成可追溯的证据 | 白 |
| `capabilities` | `#/capabilities` | 能力 · 星牧智控 | 白 + 薄雾 |
| `evidence` | `#/evidence` | 数据与边界 · 星牧智控 | 星夜 |
| `about` | `#/about` | 关于 · 星牧智控 | 白 |

### 5.4 切换行为（逐条实现，缺一条就算没做完）

1. 首次加载读 `location.hash`；未知或空 → 用 `history.replaceState` 归一到 `#/home`（不触发 hashchange）。
2. 点击任意 `[data-route]` → `preventDefault`，执行 `go(key)`；地址栏用 `history.pushState` 更新，浏览器后退/前进能回到之前的视图。
3. 当前激活视图：`.view.is-active`，其余 `hidden` + `display:none`；**任何时刻 `.view.is-active` 必须恰好 1 个**。
4. 切换动画 ≤ 600ms：旧视图先 `opacity→0, y→-12`（180ms），**动画完成后**才 `hidden`；新视图取消 `hidden` 后 `opacity 0→1, y 16→0`（420ms，`power3.out`）。两段不允许同时操作新旧视图的布局（旧视图在 180ms 后才隐藏，动画期间它仍然占位，所以新视图用 `position:absolute` 覆盖会跳动——推荐「旧视图隐藏 → 再显示新视图」的顺序，页面短暂空白可接受，胜在稳定）。
5. 切换完成时：滚动位置归零（Lenis 立即 `scrollTo(0,{immediate:true})`，无 Lenis 时 `window.scrollTo(0,0)`）；`document.title` 更新；导航 `aria-current` 更新；焦点移到新视图 `<h1 tabindex="-1">`。
6. **销毁上一视图的 ScrollTrigger**（用 `gsap.context` 包住每个视图的触发器，离开时 `ctx.revert()`），否则回去后 pin 与 scrub 会错乱。这是本页最容易做错的地方，必须验证。
7. 进入某视图时重建该视图的入场动画、计数器、手风琴状态（手风琴默认展开第 1 格）、页脚触发器刷新（`ScrollTrigger.refresh()`）。
8. 快速连点导航不叠加动画：用 `busy` 标记或 `gsap.killTweensOf(view)`，任何情况下不能出现两个激活视图或空白。
9. 跨视图锚点（导航「预约演示」）：先切到 `home`，再 `lenis.scrollTo('#cta')`；若目标不存在则停在页首。
10. 深链分享：`#/evidence` 直接打开星夜页并可继续切换；`history.back()` 能逐页回退。
11. 无障碍：切换后向 `aria-live="polite"` 的隐藏区域播报「已切换到 能力 页」。
12. 无 GSAP 时：直接显示/隐藏视图，不报错（所有动效外层套 `if (window.gsap)`）。

页面里放一个播报容器（视觉隐藏）：

```html
<p id="routeAnnouncer" class="sr-only" role="status" aria-live="polite"></p>
```

切换时写入「已切换到 能力 页」，清空后延迟 30ms 再写，保证重复切换也能被读屏识别。

### 5.5 视图 DOM 骨架

每个视图**只有一个 `h1`**（即页面可见标题），这样既能被读屏正确朗读，也是路由切换后的焦点目标：

```html
<section class="view" id="view-home" data-view="home" aria-labelledby="homeTitle">
  <h1 class="split hero-title" id="homeTitle" tabindex="-1">让每一段牧场视频<br>都变成<em>可追溯的证据。</em></h1>
  <div class="hero">…</div>
</section>

<section class="view" id="view-capabilities" data-view="capabilities" aria-labelledby="capTitle">
  <h1 class="h2 split" id="capTitle" tabindex="-1">从画面到结论，<br>每一步都留痕。</h1>
  …
</section>
```

- 首页 `h1` 就是 `.hero-title`；其余三页的 `h1` 借用 `.h2` 的视觉样式。
- 视图内其它标题用 `h2`（例如首页价值区的「不是多一个摄像头…」）。不要为了动画再补一个隐藏 `h1`。

每个视图必须是 `position:relative`，且非激活视图彻底不参与布局：

```css
.view{position:relative}
.view[hidden]{display:none}
```

---

## 6. 视图一：首页 `#/home`

### 6.1 Hero（`100svh`，`min-height:640px`，`overflow:hidden`）

元素顺序：两团飘动云 → 大标题 → 副文案 → 双按钮 → 场景画面（底部 66%）→ HUD → 磨砂方块 → 滚动提示。

```html
<div class="hero">
  <div class="cloud cloud-l"><div class="cloud-shape drift-a"></div></div>
  <div class="cloud cloud-r"><div class="cloud-shape drift-b"></div></div>

  <div class="hero-copy" data-intro>
    <span class="pill reveal">牧场视频 · 行为识别 · 风险辅助筛查</span>
    <h1 class="split hero-title" id="homeTitle" tabindex="-1">让每一段牧场视频<br>都变成<em>可追溯的证据。</em></h1>
    <p class="hero-sub reveal">识别牛只、读懂行为、留痕每一次复核 —— 让牧场里的判断有画面、有秒数、有人负责。</p>
    <div class="hero-actions reveal">
      <a class="btn" href="#/home" data-route="home" data-anchor="#cta">预约演示</a>
      <a class="btn btn-ghost" href="#/capabilities" data-route="capabilities">看看它能做什么 →</a>
    </div>
  </div>

  <div class="hero-media">
    <svg class="scene" id="heroScene" viewBox="0 0 1600 900" preserveAspectRatio="xMidYMid slice" aria-hidden="true">…</svg>
    <div class="hud" aria-hidden="true">
      <span class="hud-rec"><i></i>REC 09:41:27</span>
      <span class="hud-count">跟踪目标 <b>04</b> · 育肥 3 号栏</span>
      <span class="det" style="left:19%;top:56%;width:13%;height:17%;--t:ID 12 · 站立反刍"></span>
      <span class="det" style="left:45%;top:60%;width:12%;height:15%;--t:ID 15 · 采食"></span>
      <span class="det" style="left:68%;top:57%;width:14%;height:17%;--t:ID 18 · 卧姿休息"></span>
      <span class="scan"></span>
    </div>
  </div>

  <div class="hero-glass" id="heroGlass" aria-hidden="true"></div>
  <div class="scroll-hint" aria-hidden="true"><span></span>向下滚动</div>
</div>
```

```css
.hero{position:relative;height:100svh;min-height:640px;overflow:hidden;background:#fff}
.hero-copy{position:absolute;z-index:6;top:23%;width:100%;display:flex;flex-direction:column;
  align-items:center;gap:14px;padding:0 16px;text-align:center}
.hero-title{font-size:clamp(36px,5.4vw,76px);font-weight:400;letter-spacing:-.045em;line-height:1.06}
.hero-title em{font-style:normal;font-weight:600;color:var(--olive)}
/* 中文不用假斜体；下划线画在每个词上，拆词后不会被撕成碎块 */
.hero-title em .w{box-shadow:inset 0 -.28em 0 rgba(180,205,82,.42)}
.hero-sub{max-width:520px;font-size:14px;line-height:1.6;color:#3a402f}
.hero-actions{display:flex;gap:10px;margin-top:4px}
.hero-media{position:absolute;left:0;right:0;bottom:0;height:66%;z-index:2;
  -webkit-mask-image:linear-gradient(to bottom,transparent 0,#000 22%);
  mask-image:linear-gradient(to bottom,transparent 0,#000 22%)}
.hero-media .scene{width:100%;height:100%}
```

**云（自绘，替代原版云 PNG）**：`.cloud` 绝对定位，`cloud-l` 左上（`top:-4%;left:-6%;width:min(44vw,640px)`），`cloud-r` 右上（`top:3%;right:-7%;width:min(42vw,620px)`）；`cloud-shape` 用三层不规则白色椭圆 + `blur(18px)` + `opacity .85` 组成，直接写内联 `background: radial-gradient(...)` 或内联 SVG。右侧云形状镜像左侧。

**Hero 场景 SVG（`#heroScene`）**：这是最重要的视觉，必须画出来而不是留空。层次从后到前：

1. 天空渐变：`#fbfdf4 → #e9f3d6 55% → #d3e6b0`（`linearGradient`）。顶部接近纯白，保证文字可读。
2. 暖阳：`cx=1150 cy=180 r=120` 的径向渐变光晕（`#f8edc8` → 透明），`opacity .9`。
3. 远山：低饱和 `#c8dca4`，`opacity .85`，一串贝塞尔山脊，山脚压到画布底。
4. 中景草坡：`#a8c271`；前景草地：`#7fa144`，底部再叠 `#6b8f39`。
5. 栅栏：木桩（`stroke #5c6d3a`）+ 两道横杆，横跨中景，`opacity .55`。
6. 草叶与小花：前景撒 20~30 条细 `path`（2~3px 宽，`#5f8430`）与零星白色小圆点（`#f4f7e8`，`opacity .8`）。
7. 牛群：复用 `<g id="cow">` 剪影，3 头（`class="cow cow-1/2/3"`），位置约 `x=330/700/1030`，基线 `y≈690`，缩放 `0.85/1/1.1`，颜色 `#3d4b23`，背部高光 `#5a6b34 opacity .6`。牛只做 6~9s 的极小幅度左右位移（±30px，yoyo），不要真跑。
8. 水彩噪点：`feTurbulence` + `feColorMatrix`，`opacity .04`，布满全图。

`<g id="cow">` 剪影（可直接用，可微调）：

```html
<g id="cow">
  <path d="M14 44c0-16 12-26 30-26h40c22 0 36 10 36 26v8c0 12-10 20-26 20H38c-16 0-24-8-24-20z" fill="#3d4b23"/>
  <path d="M118 20h26c10 0 16 7 16 17v6c0 11-7 17-17 17h-21c-8 0-14-6-14-14V34c0-8 4-14 10-14z" fill="#323f1c"/>
  <path d="M158 26c6-2 10 1 10 6s-4 8-9 8" fill="none" stroke="#323f1c" stroke-width="3" stroke-linecap="round"/>
  <circle cx="140" cy="34" r="2.2" fill="#0f1508"/>
  <path d="M118 20l-10-12M132 18l4-12" stroke="#2b3617" stroke-width="5" stroke-linecap="round"/>
  <path d="M40 70v6M62 70v6M112 70v6M136 70v6" stroke="#2b3617" stroke-width="7" stroke-linecap="round"/>
  <path d="M18 38c-8 4-10 14-4 18" fill="none" stroke="#3d4b23" stroke-width="4" stroke-linecap="round"/>
  <path d="M60 30c8-4 18-4 26 0" fill="none" stroke="#5a6b34" stroke-width="4" stroke-linecap="round" opacity=".65"/>
</g>
```

**HUD（HTML 覆盖层）**：识别框 `.det` 用 `border:1px solid #8fbf2a` + 四角短凸起（`::before/::after` 做 corner ticks）+ 左上角小标签（内容取 `--t`，`font-size:11px;background:#3f5510;color:#f0f6e2;padding:2px 6px;border-radius:5px`）。扫描线 `.scan`：一条 1px 横向亮线，6s 内从上到下缓慢往返，`opacity .35`。

```css
.hud{position:absolute;inset:0;z-index:3;pointer-events:none;font-size:11px;color:#eff5e0}
.hud-rec{position:absolute;left:20px;top:20px;display:inline-flex;align-items:center;gap:6px;
  padding:4px 9px;border-radius:999px;background:rgba(18,28,10,.55);
  -webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px);letter-spacing:.04em}
.hud-rec i{width:6px;height:6px;border-radius:50%;background:#e4604f;animation:twinkle 1.6s infinite}
.hud-count{position:absolute;right:20px;top:20px;padding:4px 9px;border-radius:999px;
  background:rgba(18,28,10,.45)}
.det{position:absolute;border:1px solid #8fbf2a;border-radius:4px;opacity:.9}
.det::after{content:var(--t);position:absolute;left:-1px;top:-22px;
  font-size:10.5px;white-space:nowrap;background:#3f5510;color:#f0f6e2;padding:2px 6px;border-radius:5px}
```

小屏（≤760px）HUD 只保留 `hud-rec` 与 `hud-count`，`.det` 隐藏，避免糊成一团。

**磨砂方块 `#heroGlass`**：JS 生成，位置 `[x%, y%]`：左侧簇 `[4,54],[4,61],[8,61],[12,61],[4,68]`、`[0,60]`；中部 `[46,66],[49,70],[49,66],[52,66]`；右侧 `[86,48],[86,57],[82,66],[89,66],[86,74]`。中部的用 `clamp(28px,3.4vw,44px)`，其余 `clamp(36px,5.4vw,74px)`，`aspect-ratio:1`。移动端隐藏所有奇数下标的方块。无 reduced-motion 时：`opacity .15` 的目标值 + `duration .9` + `yoyo repeat:-1` + 随机 delay 0~3 / repeatDelay 1~4，做「呼吸式玻璃」。

### 6.2 场景条 + 价值卡片

```html
<div class="section scene-strip">
  <span class="pill reveal">适配场景</span>
  <ul class="chips reveal">
    <li>育肥牛舍</li><li>奶牛场</li><li>繁育场</li><li>家庭牧场</li><li>合作社</li><li>教学演示</li>
  </ul>
  <p class="note reveal">固定机位、一段完整视频即可开始。不替代兽医诊断与现场核查。</p>
</div>
```

```css
.section{position:relative;padding:clamp(64px,10vh,120px) 16px;display:flex;flex-direction:column;
  align-items:center;gap:clamp(18px,3vh,30px)}
.scene-strip{gap:16px;background:var(--mist)}
.chips{display:flex;flex-wrap:wrap;justify-content:center;gap:8px;list-style:none}
.chips li{font-size:13px;padding:7px 14px;border-radius:999px;background:#fff;border:1px solid var(--line);
  color:#39422a}
.note{font-size:12.5px;color:#6b7358;text-align:center}
```

价值卡片 4 张（`grid`，桌面 4 列，≤900px 2 列，≤560px 1 列）：

```html
<div class="section value-grid">
  <span class="pill reveal">它解决什么</span>
  <h2 class="h2 split">不是多一个摄像头，<br>是每一句结论都有出处。</h2>
  <div class="cards4">
    <article class="value-card reveal">
      <span class="v-ico">…内联 SVG 30×30…</span>
      <h3>行为看得见</h3>
      <p>采食、饮水、站立反刍、卧姿休息四类标签，按视频内个体汇总时长。</p>
    </article>
    <!-- 证据拿得出 / 复核对得上 / 存栏说得清 -->
  </div>
</div>
```

文案（照抄）：
1. **行为看得见** — 采食、饮水、站立反刍、卧姿休息四类标签，按视频内个体汇总时长。
2. **证据拿得出** — 每条规则提示带秒数、截图与前后片段，一键回到原视频核对。
3. **复核对得上** — 漏检、误报、ID 切换与现场关注都能人工留痕，结论只写人确认的部分。
4. **存栏说得清** — 登记数、清点数与拍摄覆盖分栏记录，差额只进复点，不自动判定丢失。

```css
.cards4{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;width:min(1080px,100%)}
.value-card{background:#fff;border:1px solid var(--line);border-radius:20px;padding:22px;
  display:flex;flex-direction:column;gap:9px;box-shadow:var(--soft)}
.value-card h3{font-size:16px;font-weight:600;letter-spacing:-.02em}
.value-card p{font-size:13px;line-height:1.6;color:#4a5140}
.v-ico{width:34px;height:34px;border-radius:11px;background:var(--pill);display:grid;place-items:center;color:var(--olive)}
```

### 6.3 流程条

```html
<div class="section flow">
  <ol class="flow-row">
    <li><b>01</b><span>上传或接入视频</span></li>
    <li><b>02</b><span>识别 · 跟踪 · 行为摘要</span></li>
    <li><b>03</b><span>人工复核与处置闭环</span></li>
  </ol>
  <a class="btn btn-ghost reveal" href="#/capabilities" data-route="capabilities">了解完整流程 →</a>
</div>
```

### 6.4 CTA（星夜，带表单）

`section#cta`：`min-height:720px`，背景 `--night`，内含夜空场景、18 个萤火光点、玻璃卡片、真实可用的留资表单。

```html
<section class="cta" id="cta" aria-labelledby="ctaTitle">
  <div class="night-scene" id="nightScene" aria-hidden="true">
    <svg viewBox="0 0 1600 900" preserveAspectRatio="xMidYMid slice">
      <defs>
        <linearGradient id="nSky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#07101f"/><stop offset=".55" stop-color="#0e2438"/>
          <stop offset="1" stop-color="#12354a"/>
        </linearGradient>
        <linearGradient id="nLake" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stop-color="#1b4a5f"/><stop offset="1" stop-color="#081726"/>
        </linearGradient>
      </defs>
      <rect width="1600" height="900" fill="url(#nSky)"/>
      <circle cx="1220" cy="180" r="86" fill="#f4ead0" opacity=".92"/>
      <circle cx="1220" cy="180" r="150" fill="#f4ead0" opacity=".12"/>
      <path d="M0 560 260 430 520 545 760 415 1040 555 1280 470 1600 560 1600 900 0 900Z" fill="#0a1b2c"/>
      <path d="M0 700 300 620 620 690 900 615 1200 700 1600 640 1600 900 0 900Z" fill="#081525"/>
      <path d="M0 760H1600V900H0Z" fill="url(#nLake)"/>
      <g opacity=".5" stroke="#cfe3d6" stroke-width="2" stroke-linecap="round">
        <path d="M1080 790h180M1040 812h240M1100 834h150"/>
      </g>
      <g fill="#0b1c2c" opacity=".95">
        <use href="#cow" x="380" y="742" transform="scale(.5)"/>
        <use href="#cow" x="520" y="750" transform="scale(.42)"/>
      </g>
    </svg>
  </div>
  <div class="fireflies" id="fireflies" aria-hidden="true"></div>

  <div class="cta-card" id="ctaCard">
    <span class="pill">开始</span>
    <h2 class="h2 split" id="ctaTitle">先看一段真实视频，<br>再决定要不要用。</h2>
    <p class="cta-copy reveal">留下邮箱，我们发你一份演示视频与验收说明；只用项目联系，不公开。</p>
    <form class="lead-form" novalidate>
      <label class="sr-only" for="ctaEmail">邮箱</label>
      <input id="ctaEmail" type="email" name="email" placeholder="name@farm.cn" autocomplete="email" />
      <button class="btn" type="submit">获取演示</button>
    </form>
    <p class="form-msg" role="status" aria-live="polite"></p>
    <p class="cta-note">科研原型 · 大学生创新创业训练计划项目</p>
  </div>
</section>
```

```css
.cta{position:relative;min-height:720px;overflow:hidden;background:var(--night);
  display:flex;align-items:center;justify-content:center;padding:14vh 16px 12vh}
.night-scene{position:absolute;inset:0;z-index:1}
.night-scene svg{width:100%;height:118%;object-fit:cover}
.fireflies{position:absolute;inset:0;z-index:2;pointer-events:none;overflow:hidden}
.firefly{position:absolute;top:-20px;border-radius:50%;
  background:radial-gradient(circle,#fff8dd 0%,#f3d98a 45%,rgba(243,217,138,0) 72%);
  box-shadow:0 0 12px rgba(245,227,173,.85);opacity:.9;
  animation:fall var(--dur) linear infinite}
.cta-card{position:relative;z-index:4;width:min(600px,calc(100% - 8px));padding:40px 28px 34px;
  text-align:center;border-radius:26px;border:1px solid rgba(255,255,255,.16);
  background:linear-gradient(to bottom,rgba(255,255,255,.14),rgba(255,255,255,.05));
  -webkit-backdrop-filter:blur(18px) saturate(1.2);backdrop-filter:blur(18px) saturate(1.2);
  box-shadow:0 30px 60px rgba(0,0,0,.35);color:#eaf2df;display:flex;flex-direction:column;
  align-items:center;gap:12px}
.cta-card .h2{font-size:clamp(24px,2.8vw,38px);margin:6px 0 2px;color:#f6faee}
.cta-copy{font-size:13.5px;line-height:1.6;color:#c9d6c3;max-width:420px}
.cta-note{font-size:11px;color:#8fa48f;margin-top:2px}
.lead-form{display:flex;gap:8px;width:min(420px,100%);margin-top:4px}
.lead-form input{flex:1;height:36px;padding:0 14px;border-radius:999px;border:1px solid rgba(255,255,255,.3);
  background:rgba(255,255,255,.1);color:#f4f8ee;font-size:13px;outline:none;min-width:0}
.lead-form input::placeholder{color:#9fb09c}
.lead-form input:focus{border-color:var(--lime);box-shadow:0 0 0 3px rgba(180,205,82,.25)}
.lead-form input[aria-invalid="true"]{border-color:#e88b7a}
.form-msg{font-size:12px;min-height:16px;color:#d9e6cc}
.form-msg.is-error{color:#ffb3a4}
```

表单行为（必须真做）：
- 空值 → `"请先填写邮箱"`；格式不符（`/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/`）→ `"邮箱格式看起来不对"`；错误时 `aria-invalid="true"`，不弹出 `alert`。
- 通过 → 按钮 `disabled` + 文案「提交中…」0.6s → 写入 `localStorage.setItem('xingmu-lead', JSON.stringify({email,ts}))` → 成功态 `"已收到，我们会尽快联系你。"`，输入框清空、按钮恢复。重复提交会覆盖同一条记录（不做假后端）。
- 键盘 Enter 可提交；`aria-live` 会被读屏播报。

---

## 7. 视图二：能力 `#/capabilities`

结构：页头 → 三面板手风琴（全屏高）→ 六张能力卡 → 边界提示块。

### 7.1 页头

```html
<header class="view-head">
  <span class="pill reveal">能力矩阵</span>
  <h1 class="h2 split" id="capTitle" tabindex="-1">从画面到结论，<br>每一步都留痕。</h1>
  <p class="view-sub reveal">四个能力互相咬合：识别准不准，靠证据回看；结论算不算数，靠人复核。</p>
</header>
```

```css
.view-head{display:flex;flex-direction:column;align-items:center;gap:14px;
  padding:clamp(110px,14vh,150px) 16px clamp(20px,4vh,40px);text-align:center}
.view-sub{font-size:14px;line-height:1.6;color:#4d5443;max-width:520px}
```

### 7.2 三面板手风琴（`section#track`）

不是横向滚动，而是三块竖版面板，一列展开、两列压成窄条并裁切超大数字。**桌面 ≥761px 才启用交互；移动端退化成三张堆叠卡片。**

```html
<section class="loop" id="loop" aria-label="工作流程">
  <div class="loop-head">
    <span class="pill reveal">工作流程</span>
    <h2 class="h2 split">一段视频，<br>三步交到你手里。</h2>
  </div>
  <div class="track" id="track" role="tablist" aria-label="三步流程">
    <div class="panel is-active" role="tab" tabindex="0" aria-selected="true" aria-label="第 1 步：接入与拍摄检查">
      <div class="panel-in">
        <span class="num" aria-hidden="true">01</span>
        <div class="step">
          <h3>接入与拍摄检查</h3>
          <p>固定机位、一段完整视频就能开始。读取时长与分辨率，画面过短或过糊时提示补拍，但不替你判断覆盖范围。</p>
          <div class="mini-evidence glass" aria-hidden="true">…拍摄检查小卡…</div>
        </div>
      </div>
    </div>
    <!-- 02 识别、跟踪与行为摘要（绿色 num） -->
    <!-- 03 人工复核与处置闭环（lime num） -->
  </div>
</section>
```

```css
.loop{position:relative;height:100vh;min-height:680px;overflow:hidden;background:#fff}
.loop-head{position:absolute;z-index:4;top:12vh;left:0;right:0;display:flex;flex-direction:column;
  align-items:center;gap:14px;padding:0 16px;text-align:center}
.track{position:absolute;inset:0;display:flex}
.panel{position:relative;flex:0 0 clamp(96px,11vw,170px);height:100%;overflow:hidden;
  border-right:1px solid var(--line);cursor:pointer;outline:none;
  transition:flex-grow .9s cubic-bezier(.77,0,.18,1),background .4s}
.panel:last-child{border-right:0}
.panel:hover{background:rgba(243,247,234,.6)}
.panel.is-active{flex-grow:1;cursor:default;background:#fff}
.panel-in{position:absolute;left:clamp(14px,1.8vw,28px);bottom:10vh;display:flex;align-items:flex-end;
  gap:clamp(16px,2vw,30px);width:max-content}
.num{font-size:clamp(170px,36vh,380px);font-weight:600;line-height:.74;letter-spacing:-.07em}
.panel:nth-child(1) .num{color:var(--olive)}
.panel:nth-child(2) .num{color:var(--green)}
.panel:nth-child(3) .num{color:var(--lime)}
.step{position:relative;width:min(400px,30vw);padding-bottom:4px;opacity:0;transform:translateX(-24px);
  filter:blur(6px);transition:opacity .4s,transform .5s,filter .4s}
.panel.is-active .step{opacity:1;transform:none;filter:none;
  transition:opacity .7s .4s,transform .9s .35s cubic-bezier(.2,.8,.2,1),filter .7s .4s}
.step h3{font-size:clamp(20px,1.7vw,26px);font-weight:400;letter-spacing:-.03em;margin-bottom:10px}
.step p{font-size:14px;line-height:1.55;color:#2b2e27}
.mini-evidence{position:relative;margin-top:18px;width:min(240px,22vw);padding:10px 12px;border-radius:12px;
  background:rgba(255,255,255,.7);border:1px solid #e3ebd2;color:#3f4a2c;font-size:11.5px;
  display:flex;flex-direction:column;gap:4px;animation:driftA 9s ease-in-out infinite alternate}
```

三格文案（照抄）：
1. **接入与拍摄检查**：固定机位、一段完整视频就能开始。读取时长与分辨率，画面过短或过糊时提示补拍，但不替你判断覆盖范围。
2. **识别、跟踪与行为摘要**：YOLO11 检测 + ByteTrack 跟踪，按视频内 Track ID 汇总四类行为时长；规则提示附秒数、截图与片段，随时回看。
3. **人工复核与处置闭环**：漏检、误报、ID 切换与现场关注由人记录；核查事项可指派、复查、关闭，最后生成一页巡检摘要。

小卡内容分别写：
- 第 1 格：`拍摄检查` / `21 秒 · 640×640` / `建议补拍：否`
- 第 2 格：`ID 12` / `站立反刍 19.5 s` / `规则：活动量下降`
- 第 3 格：`待办 #08` / `现场复核 ID 12` / `明日复查`

交互（桌面）：
- `mouseenter`（`matchMedia('(pointer:fine)')` 且 `min-width:761px`）、`focus`、`click` 都调用 `activate(panel)`，并把其余面板的 `aria-selected` 置 `false`。
- 键盘：`←/→` 在面板间移动并激活，`Home/End` 到首尾，`Enter/Space` 激活。
- 激活后只允许一个 `.is-active`；最近悬停的面板保持展开。

移动端（≤760px）：
```css
.loop{height:auto;min-height:0;padding:12vh 0 40px}
.loop-head{position:static;top:auto;margin-bottom:24px}
.track{position:static;inset:auto;flex-direction:column;margin-top:20px}
.panel{flex:none;height:auto;overflow:visible;border-right:0;border-top:1px solid var(--line);
  cursor:auto;padding:0}
.panel-in{position:static;left:auto;bottom:auto;width:auto;padding:26px 16px;
  display:flex;align-items:center;gap:16px}
.num{font-size:64px;line-height:1;letter-spacing:-.05em}
.step{opacity:1;transform:none;filter:none;width:auto;flex:1}
.mini-evidence{display:none}
```

### 7.3 六张能力卡

```css
.cap-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;width:min(1080px,100%)}
.cap-card{background:#fff;border:1px solid var(--line);border-radius:20px;padding:22px;
  display:flex;flex-direction:column;gap:8px;transition:transform .3s,box-shadow .3s}
.cap-card:hover{transform:translateY(-3px);box-shadow:var(--soft)}
.cap-card h3{font-size:15.5px;font-weight:600;letter-spacing:-.02em}
.cap-card p{font-size:13px;line-height:1.6;color:#4a5140}
@media (max-width:900px){.cap-grid{grid-template-columns:repeat(2,1fr)}}
@media (max-width:560px){.cap-grid{grid-template-columns:1fr}}
```

文案（照抄）：
1. **视频识别与跟踪** — YOLO11 检测 + ByteTrack 跟踪，输出带框视频、轨迹 CSV 与视频内 Track ID。
2. **行为时长摘要** — 四类行为逐个体汇总；判不准的片段单列，不硬猜。
3. **健康风险辅助筛查** — 静止、离群、活动量下降等规则评分，只作为核查线索。
4. **圈舍存栏核对** — 登记数、清点数、拍摄覆盖分栏记录；差额先进「待复点」。
5. **区域与栏门事件** — 在固定机位上画采食区、饮水区与栏门线，统计进入次数与穿线方向。
6. **处置闭环与巡检摘要** — 从视频提示一键生成核查事项，记录处理、复查、关闭，并导出摘要。

### 7.4 边界提示块

```html
<aside class="boundary reveal" aria-label="能力边界">
  <h3>边界写清楚，结论才可信。</h3>
  <ul>
    <li>只输出核查线索，不做疾病诊断，也不预测发病时间。</li>
    <li>视频内 Track ID 只在本段视频有效，不跨视频认同一头牛。</li>
    <li>存栏差额需人工复点与出入栏台账核对，算法不判定丢失。</li>
    <li>结果用于辅助筛查，不替代兽医与现场判断。</li>
  </ul>
</aside>
```

```css
.boundary{width:min(1080px,100%);border-radius:20px;background:var(--mist);border:1px solid #e4ecd4;
  padding:24px;display:flex;flex-direction:column;gap:12px}
.boundary h3{font-size:15px;font-weight:600;letter-spacing:-.01em}
.boundary ul{list-style:none;display:grid;gap:8px}
.boundary li{position:relative;padding-left:16px;font-size:13px;line-height:1.6;color:#4a5140}
.boundary li::before{content:"";position:absolute;left:0;top:8px;width:6px;height:6px;border-radius:50%;
  background:var(--green)}
```

---

## 8. 视图三：数据与边界 `#/evidence`（星夜）

整页深蓝，顶部星空，核心是「先数字、后边界」：一张会随滚动计数的票券卡组（桌面 pin），加两张表。

```css
#view-evidence{background:var(--night);color:#e9f0e2}
#view-evidence .h2{color:#f7fae9}
#view-evidence .pill{background:rgba(180,205,82,.16);color:#d8e8a8}
#view-evidence .view-sub{color:#b9c6b6}
.evidence-stars{position:absolute;inset:0;pointer-events:none;overflow:hidden}
.star{position:absolute;border-radius:50%;background:#f6eccd;animation:twinkle 4s ease-in-out infinite}
```

### 8.1 页头

```html
<header class="view-head">
  <span class="pill reveal">数据与边界</span>
  <h1 class="h2 split" id="evTitle" tabindex="-1">先把能力摆出来，<br>再说清它不能做什么。</h1>
  <p class="view-sub reveal">数字来自开发样例，不来自牧场验收；我们把口径写在页面上，方便你核对。</p>
</header>
```

### 8.2 计数区（桌面 pin）

```html
<section class="stats" id="statsPin" aria-label="关键指标">
  <div class="sq-field" data-count="22" aria-hidden="true"></div>
  <div class="stats-inner">
    <span class="pill reveal">开发样例</span>
    <h2 class="h2 split">从一段视频里，<br>能读出这些东西。</h2>
    <div class="cards">
      <article class="card stat-card" data-to="4" data-dec="0" data-suf=" 类">
        <span>行为标签</span><b>0 类</b>
      </article>
      <article class="card stat-card" data-to="26" data-dec="0" data-suf=" 个">
        <span>视频内 Track ID</span><b>0 个</b>
      </article>
      <article class="card stat-card" data-to="100" data-dec="0" data-suf="%">
        <span>规则提示可回看</span><b>0%</b>
      </article>
      <article class="card stat-card" data-to="100" data-dec="0" data-suf="%">
        <span>人工复核留痕</span><b>0%</b>
      </article>
    </div>
    <div class="cards-shadow" aria-hidden="true"></div>
    <div class="herd-wrap" aria-hidden="true">
      <svg class="herd" id="herd" viewBox="0 0 520 300">
        <path d="M0 262h520" stroke="#8fb14f" stroke-width="2" opacity=".5"/>
        <!-- 3 头牛剪影 + 栅栏，复用 #cow -->
      </svg>
    </div>
    <div class="sources-wrap">
      <div class="band" id="band" aria-hidden="true"></div>
      <ul class="sources">
        <li><b>WAID4500</b><span>检测基线</span></li>
        <li><b>CBVD-4</b><span>行为四分类</span></li>
        <li><b>ICAERUS</b><span>跨物种样本</span></li>
      </ul>
    </div>
  </div>
</section>
```

```css
.stats{position:relative;min-height:100vh;overflow:hidden;padding:8vh 16px}
.sq-field{position:absolute;inset:0 0 auto 0;height:42%;z-index:1;pointer-events:none;
  -webkit-mask-image:linear-gradient(#000,transparent);mask-image:linear-gradient(#000,transparent)}
.stats-inner{position:relative;z-index:3;min-height:calc(100vh - 16vh);display:flex;
  flex-direction:column;align-items:center;justify-content:center;gap:20px;text-align:center}
.cards{position:relative;z-index:4;display:grid;grid-template-columns:repeat(4,1fr);gap:12px;
  width:min(880px,100%)}
.card{height:150px;padding:18px 22px;border-radius:22px;background:var(--lime);
  display:flex;flex-direction:column;justify-content:space-between;text-align:left;
  -webkit-mask:
    radial-gradient(circle 17px at 0 55%,#0000 97%,#000) left/51% 100% no-repeat,
    radial-gradient(circle 17px at 100% 55%,#0000 97%,#000) right/51% 100% no-repeat;
  mask:
    radial-gradient(circle 17px at 0 55%,#0000 97%,#000) left/51% 100% no-repeat,
    radial-gradient(circle 17px at 100% 55%,#0000 97%,#000) right/51% 100% no-repeat}
.card span{font-size:10.5px;font-weight:500;color:#2a3410;letter-spacing:.01em}
.card b{font-size:clamp(30px,3.4vw,44px);font-weight:600;letter-spacing:-.04em;color:#151a08;
  font-variant-numeric:tabular-nums}
.cards-shadow{width:min(820px,94%);height:10px;margin-top:-14px;border-radius:50%;z-index:3;
  background:radial-gradient(closest-side,rgba(0,0,0,.3),transparent)}
.sources-wrap{position:relative;z-index:6;width:100%;display:flex;justify-content:center}
.sources{position:relative;z-index:6;display:flex;gap:26px;list-style:none;margin-top:4px;padding:10px 12px}
.sources li{display:flex;flex-direction:column;gap:2px;font-size:11px;color:#a9bba4}
.sources b{font-size:13px;font-weight:600;color:#e6f0d6;letter-spacing:.01em}
@media (max-width:900px){.cards{grid-template-columns:repeat(2,1fr)}.card{height:120px}
  .stats{min-height:0;padding:10vh 16px 12vh}}
@media (max-width:560px){.cards{grid-template-columns:1fr}.sources{flex-wrap:wrap;justify-content:center}}
```

- `.herd-wrap`：`position:absolute;left:50%;bottom:-4%;transform:translateX(-50%);width:min(360px,70vw);z-index:2;pointer-events:none`；`#herd{width:100%;height:auto}`。只画剪影（3 头牛 + 栅栏 + 地面线），颜色 `#8fb14f` / `#a7c76a`，可用 `filter:blur(.6px)` 出一点水彩边。
- `.sources-wrap`：`position:relative;z-index:6;display:flex;justify-content:center;align-items:center`。
- `.band`：**必须包在 `.sources-wrap` 里**，`position:absolute;left:50%;top:-6px;transform:translateX(-50%);width:min(340px,58vw);height:64px;z-index:5;pointer-events:none;backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);background:rgba(255,255,255,.06);-webkit-mask-image:linear-gradient(90deg,transparent,#000 18%,#000 82%,transparent);mask-image:linear-gradient(90deg,transparent,#000 18%,#000 82%,transparent)`。它的作用是让牛群从数据来源后面经过时被柔化。移动端 `display:none`。

### 8.3 数据来源表

```html
<div class="section dark-section">
  <span class="pill reveal">数据来源</span>
  <h2 class="h2 split">每一段数据，都能说清来路。</h2>
  <div class="table-wrap reveal">
    <table class="data-table">
      <thead><tr><th>数据集</th><th>用途</th><th>边界</th></tr></thead>
      <tbody>
        <tr><td>WAID4500</td><td>目标检测基线</td><td>公开图像集，不代表牧场视频泛化</td></tr>
        <tr><td>CBVD-4</td><td>行为四分类验证</td><td>站立反刍仍是最弱类</td></tr>
        <tr><td>ICAERUS 羊视频</td><td>跨物种外部样本</td><td>存在域差异，仅用于暴露问题</td></tr>
      </tbody>
    </table>
  </div>
  <p class="table-note reveal">开发样例：210 帧、26 个视频内 ID、26 条规则提示。用于演示链路，不作为牧场验收结论。</p>
</div>
```

### 8.4 能力边界表

```html
<div class="table-wrap reveal">
  <table class="data-table">
    <thead><tr><th>维度</th><th>系统能给出</th><th>系统不能给出</th></tr></thead>
    <tbody>
      <tr><td>个体跟踪</td><td>视频内 Track ID 与轨迹</td><td>跨视频自动识别同一头牛</td></tr>
      <tr><td>行为</td><td>四类行为时长与不确定片段</td><td>疾病或疼痛判定</td></tr>
      <tr><td>健康</td><td>规则型风险提示与证据</td><td>发病时间预测、确诊</td></tr>
      <tr><td>存栏</td><td>计数参考与差额提醒</td><td>未经人工复点的存栏真值</td></tr>
    </tbody>
  </table>
</div>
```

```css
#view-evidence .section{gap:18px}
.table-wrap{width:min(920px,100%);border-radius:16px;background:rgba(255,255,255,.04);overflow-x:auto}
.data-table{width:100%;min-width:520px;border-collapse:collapse;font-size:13px;color:#cfdcc6;
  background:rgba(255,255,255,.04);border-radius:16px}
.data-table th{font-size:11px;font-weight:500;color:#9fb394;text-align:left;padding:12px 16px;
  border-bottom:1px solid rgba(255,255,255,.1);white-space:nowrap}
.data-table td{padding:13px 16px;border-bottom:1px solid rgba(255,255,255,.06);line-height:1.5;
  vertical-align:top}
.data-table tr:last-child td{border-bottom:0}
.data-table td:first-child{color:#eef5e0;font-weight:500}
.table-note{font-size:11.5px;color:#93a58c;text-align:center;max-width:560px}
@media (max-width:760px){.data-table{font-size:12px}.data-table th,.data-table td{padding:10px 10px}}
```

星点：JS 生成 64 个 `.star`，随机 `left/top`，尺寸 1~2.5px，`animation-delay` 随机；`prefers-reduced-motion` 下不生成。

---

## 9. 视图四：关于 `#/about`

```html
<header class="view-head">
  <span class="pill reveal">关于项目</span>
  <h1 class="h2 split" id="aboutTitle" tabindex="-1">在牧场里长出来，<br>而不是在 PPT 里想出来。</h1>
  <p class="view-sub reveal">星牧智控是大学生创新创业训练计划项目，一个可运行、可纠错、可追溯的科研原型。</p>
</header>
```

内容三块（每块 `width:min(880px,100%)`）：

1. **项目自述**（两栏文字，≤760px 变单栏）：
   - 左：「我们要解决的不是『识别一头牛』，而是『当系统说这头牛不太对时，牧场能不能查得到依据、担得起责任』。」
   - 右：「因此整条链路围绕证据组织：每条提示有秒数、有截图、有片段，复核人是人，结论由人签字。」
2. **里程碑时间线**（4 条，竖线 + 圆点，当前项高亮）：
   - 2026.06 · 本机可运行演示链路（检测、跟踪、健康规则、人工复核）
   - 2026.09 · 模块化工作台，视频证据回看与处置待办
   - 2026.10 · 圈舍核对、区域与栏门事件、巡检摘要与证据核对
   - 下一步 · 独立牧场视频与现场台账验收（进行中）
3. **技术栈 chips**：YOLO11 / ByteTrack / FastAPI / React + Vite / SQLite / 规则引擎 / Isolation Forest。下面一行小字：「检测模型与行为模型分开演进；行为模型缺失时，检测与规则分析仍可运行。」
4. **联系**：与首页表单同结构（复用 `.lead-form`，但独立 id，避免重复 id），标题「想看看它怎么跑？」，提交后写入 `localStorage` 的 `xingmu-lead`。

```css
.about-block{width:min(880px,100%);display:grid;grid-template-columns:1fr 1fr;gap:24px}
.about-block p{font-size:14px;line-height:1.75;color:#414a37}
@media (max-width:760px){.about-block{grid-template-columns:1fr;gap:14px}}
.timeline{list-style:none;width:min(880px,100%);display:grid;gap:18px;position:relative}
.timeline::before{content:"";position:absolute;left:7px;top:6px;bottom:6px;width:1px;background:#dce6c8}
.timeline li{position:relative;padding-left:30px}
.timeline li::before{content:"";position:absolute;left:0;top:6px;width:15px;height:15px;border-radius:50%;
  background:#fff;border:2px solid var(--green)}
.timeline li.is-now::before{background:var(--lime);border-color:var(--olive)}
.timeline time{font-size:11.5px;letter-spacing:.06em;color:#7b8666}
.timeline span{display:block;font-size:14px;line-height:1.6;color:#2f3726;margin-top:3px}
.stack-chips{display:flex;flex-wrap:wrap;gap:8px;justify-content:center}
.stack-chips li{list-style:none;font-size:12.5px;padding:6px 12px;border-radius:999px;
  background:#fff;border:1px solid var(--line);color:#39422a}
```

---

## 10. 页脚（全站共用，`var(--lime)` 底）

```html
<footer id="footer">
  <a class="f-logo" href="#/home" data-route="home" aria-label="星牧智控首页">
    <svg viewBox="0 0 80 80" overflow="visible" aria-hidden="true">
      <circle id="fRing" cx="40" cy="40" r="37" fill="none" stroke="#111" stroke-width="2.4"
              stroke-dasharray="233" stroke-dashoffset="233" transform="rotate(-90 40 40)"/>
      <circle class="fdot" cx="22" cy="40" r="4.5" fill="#111"/>
      <circle class="fdot" cx="40" cy="40" r="4.5" fill="#111"/>
      <circle class="fdot" cx="58" cy="40" r="4.5" fill="#111"/>
      <path id="fMark" d="M30 54 40 30 50 54" fill="none" stroke="#111" stroke-width="10"
            stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="60" stroke-dashoffset="60"/>
    </svg>
  </a>
  <nav class="f-links" aria-label="页脚导航">
    <a href="#/capabilities" data-route="capabilities">能力</a>
    <a href="#/evidence" data-route="evidence">数据与边界</a>
    <a href="#/about" data-route="about">关于</a>
    <a href="mailto:contact@example.com">邮件</a>
  </nav>
  <div class="f-social">
    <a href="#/about" data-route="about" aria-label="项目介绍">…SVG…</a>
    <a href="mailto:contact@example.com" aria-label="邮件联系">…SVG…</a>
    <a href="#/home" data-route="home" data-top aria-label="回到顶部">…SVG…</a>
  </div>
  <p class="f-copy">© 2026 星牧智控 · 大学生创新创业训练计划项目</p>
</footer>
```

- `contact@example.com` 是占位邮箱，交付时替换成项目实际邮箱；两个入口都必须是可点击的 `mailto:`。
- 页脚三个社交图标不要照搬 X / Instagram / LinkedIn，用与主题一致的三枚简单内联 SVG（叶片 / 邮件 / 向上箭头），分别指向 关于页、邮件、回到顶部。
- 「回到顶部」用 `data-top` 标记，点击执行 `lenis.scrollTo(0)`（无 Lenis 时 `window.scrollTo({top:0,behavior:'smooth'})`），**不要**用 `href="#"`。

```css
#footer{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;row-gap:22px;
  padding:34px 4vw 22px;background:var(--lime)}
.f-logo{width:72px;height:72px;justify-self:start}
.f-logo svg{width:100%;height:100%}
.f-links{display:flex;gap:24px;font-size:13px;color:#1d240c;justify-content:center}
.f-links a:hover{text-decoration:underline;text-underline-offset:3px}
.f-social{display:flex;gap:16px;justify-self:end;color:#1d240c}
.f-social svg{width:18px;height:18px}
.f-copy{grid-column:1 / -1;text-align:center;font-size:11px;color:#2a330f}
@media (max-width:760px){
  #footer{grid-template-columns:1fr;justify-items:center;text-align:center;padding:30px 16px 20px}
  .f-logo,.f-links,.f-social{justify-self:center}
  .f-links{flex-wrap:wrap;gap:16px}
}
```

页脚动画（进入视口一次，`start:"top 92%"`）：

1. `.fdot` 弹跳：`y:-8`，`duration .25`，`stagger .08`，`yoyo`，`repeat 3`，`sine.inOut`。
2. 三个点滑向左：`attr:{cx:27,cy:50}`，`.45s`，`power3.inOut`（先全部重合）。
3. 第 2、3 个点淡出（`.1s`）。
4. `#fMark` 画线：`strokeDashoffset 0`，`.6s`，`power3.out`；同时点 1 `r:5.5`（`back.out(3)`）。
5. `#fRing` 画圆：`strokeDashoffset 0`，`.9s`，`power2.inOut`，`"-=.3"` 起始。

---

## 11. JavaScript 规格

单 IIFE，`"use strict"`。顺序如下，缺一环页面就会「看起来像」但不好用。

### 11.1 初始化顺序

```js
(function () {
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const hasGsap = !!window.gsap;
  if (hasGsap && window.ScrollTrigger) gsap.registerPlugin(ScrollTrigger);
  // 1 拆词 → 2 生成云/玻璃/星点/萤火 → 3 绑定表单 → 4 Lenis → 5 路由 → 6 开场动画（或降级）→ 7 setupView
})();
```

### 11.2 拆词（`.split`）

- 递归处理 `.split` 内的文本节点；遇到 `em`、`strong` 等元素要**递归进去**保留其样式；`br` 保留。
- 中文没有空格：优先用 `Intl.Segmenter('zh',{granularity:'word'})` 切分后再包 `span.w`；不支持时回退为「每 2 个汉字一组」，**不要退化成逐字**（逐字会显得碎）。
- 纯空白文本节点原样保留，不要包 span。
- 幂等：处理后加 `data-split="1"`，避免路由重入时重复包裹。

### 11.3 Lenis

```js
const lenis = window.Lenis ? new Lenis({
  duration: 1.25,
  easing: t => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
  smoothWheel: true
}) : null;
if (lenis && hasGsap) {
  lenis.on('scroll', ScrollTrigger.update);
  gsap.ticker.add(t => lenis.raf(t * 1000));
  gsap.ticker.lagSmoothing(0);
}
```

- 开场期间 `lenis && lenis.stop()`，结束后 `lenis.start()`。
- 所有站内 `a[href^="#"]` 统一处理：若目标是路由（`#/...`）走路由；若目标是页内锚点（`#cta`）用 `lenis.scrollTo(el,{duration:1.6})`。没有 Lenis 时用 `el.scrollIntoView({behavior: reduce ? 'auto' : 'smooth'})`。

### 11.4 开场（backdrop 放大）

不写死 CSS 过渡，用 GSAP；`body.intro` 在 HTML 里预置，避免白屏闪烁。

```js
const tl = gsap.timeline({ delay: .25, onComplete(){ body.classList.remove('intro');
  gsap.set('#app',{clearProps:'all'}); backdrop.remove(); lenis && lenis.start();
  setupView(current); ScrollTrigger && ScrollTrigger.refresh(); } });

tl.fromTo('#app',{scale:.9,borderRadius:28},{scale:1,borderRadius:0,duration:1.4,ease:'expo.inOut'})
  .to('#siteNav',{opacity:1,y:0,duration:.8,ease:'power3.out'},'-=.5');

if (current === 'home') {           // 深链进入其它页时，这几段不要执行
  tl.to('.view.is-active .split .w',{opacity:1,y:0,filter:'blur(0px)',duration:1,stagger:.07,ease:'power3.out'},'-=.7')
    .fromTo('.hero-copy .reveal',{opacity:0,y:12},{opacity:1,y:0,duration:.8,stagger:.08,ease:'power3.out'},'-=.75')
    .fromTo('.cloud-l',{x:-120,opacity:0},{x:0,opacity:1,duration:1.6,ease:'power3.out'},.4)
    .fromTo('.cloud-r',{x:120,opacity:0},{x:0,opacity:1,duration:1.6,ease:'power3.out'},.4)
    .fromTo('#heroGlass .glass',{opacity:0,scale:.6},
      {opacity:1,scale:1,duration:.6,stagger:{each:.05,from:'random'},ease:'back.out(2)'},'-=1');
}
```

- 开场前 `gsap.set('#siteNav',{opacity:0,y:-16})`；仅当 `current === 'home' && !reduce` 时再把 hero 标题词设为 `{opacity:0,y:24,filter:'blur(10px)'}`。
- **避免二次淡入**：开场已经处理过 hero 标题与 `.reveal`，`setupView` 必须跳过 `.hero-copy[data-intro]` 里的元素（用 `root.querySelectorAll('.hero-copy:not([data-intro]) .reveal, ...')` 或直接排除该容器），否则首屏会闪两下。
- 若首屏不是 `home`（深链进入 `#/evidence`），只做缩放与导航；云和 hero 标题那段跳过，由 `setupView` 负责新视图入场。
- `reduce` 为真时：跳过整个时间线，直接清理 `intro` 类并调用 `setupView`。

### 11.5 路由

```js
const ROUTES = {
  home:         { sel:'#view-home',         title:'星牧智控 — 让每一段牧场视频都变成可追溯的证据' },
  capabilities: { sel:'#view-capabilities', title:'能力 · 星牧智控' },
  evidence:     { sel:'#view-evidence',     title:'数据与边界 · 星牧智控' },
  about:        { sel:'#view-about',        title:'关于 · 星牧智控' }
};
```

`go(key, {push=true, animate=true, anchor=null})`：
1. `if (key === current && !anchor) return;`
2. `key = ROUTES[key] ? key : 'home'`。
3. 旧视图淡出：`gsap.to(old,{opacity:0,y:-12,duration:.18})`，在 `onComplete` 里 `old.setAttribute('hidden','')`、移除 `.is-active`；同时 `viewCtx && viewCtx.revert()`（先杀触发器，避免滚动中触发）。
4. 显示新视图：`el.removeAttribute('hidden')`；`el.classList.add('is-active')`；`current = key`；`gsap.set(el,{opacity:0,y:12})`。
5. 滚动归零、`document.title`、导航 `aria-current`、live region 播报、`focus({preventScroll:true})` 到当前视图的 `h1`（每个视图恰好一个可见 `h1`，见 5.5）。
6. 入场：`gsap.to(el,{opacity:1,y:0,duration:.42,ease:'power3.out'})`。
7. `setupView(el)`；`ScrollTrigger && ScrollTrigger.refresh()`。
8. `push` 时 `history.pushState({view:key}, '', '#/'+key)`。
9. `anchor` 存在时，在入场完成后 `lenis.scrollTo(anchor,{duration:1.2})`；若 `prefers-reduced-motion` 直接跳转。
10. 整个流程用 `busy` 标记串行化；连续点击时丢弃中间请求（只保证最后一次生效）。

监听（两个都要，去重后再调 `go`）：

```js
let lastHash = location.hash;
const syncFromUrl = () => {
  if (location.hash === lastHash) return;
  lastHash = location.hash;
  go(location.hash.replace(/^#\//, ''), { push: false });
};
addEventListener('popstate', syncFromUrl);
addEventListener('hashchange', syncFromUrl);

document.addEventListener('click', e => {
  const a = e.target.closest('[data-route]');
  if (!a) return;
  e.preventDefault();
  go(a.dataset.route, { anchor: a.dataset.anchor || null });
});
```

`go` 内部用 `history.pushState` 更新地址后同步 `lastHash = location.hash`，否则会触发一次多余的切换。
用 `hidden` 属性 + CSS `.view[hidden]{display:none}`，保证无障碍树里只有一个页面。

### 11.6 每个视图的触发器 `setupView(root)`

统一用 `gsap.context`（无 GSAP 时直接跳过，页面内容仍可见）：

```js
viewCtx = gsap.context(() => {
  // 1 入场：.reveal → opacity 0, y 16, .8s, power3.out, start "top 85%"
  // 2 .split 词：opacity 0, y 22, blur(8px), .9s, stagger .06, start "top 80%"
  // 3 计数器 / pin（仅 evidence 视图）
  // 4 手风琴入场与交互（仅 capabilities 视图；交互绑定不受 context 影响也行）
  // 5 场景视差（仅 home 视图）
}, root);
```

分视图细节：

**home**
- Hero 视差（`trigger:'#view-home .hero'`，`start:'top top'`，`end:'bottom top'`，`scrub`）：标题 `yPercent:-60`；`.cloud-l/.cloud-r` 用 `data-par="-60"/"-90"` 的 `y`；`.hero-media` `yPercent:8`。
- 牛群：三头牛各自 `x: ±30`，`duration 7~11`，`yoyo`，`repeat:-1`，`sine.inOut`，随机起点。
- 识别框与牛群的节奏一致（同向、同时长），不要各飘各的。
- CTA：`#nightScene` `yPercent:-12→0`，`trigger:'#cta'`，`start:'top bottom'`，`end:'bottom bottom'`，`scrub`；`#ctaCard` 从 `y 80, scale .94, opacity 0, filter blur(10px)`，`1.2s power3.out`，在 `#cta top 60%` 触发。
- 入场：`.reveal` 与标题词；**跳过 `[data-intro]` 内的元素**（hero 的胶囊、副文案、按钮、标题由开场动画负责），`#heroGlass` 只在开场动画里处理，不要在 setupView 里二次闪烁。

**capabilities**
- `.panel-in`：`y 120 → 0`，`opacity 0 → 1`，`stagger .12`，`trigger:'#loop top 60%'`。
- `.panel` 交互在 11.7。
- 能力卡：`.cap-card` 依次 `y 30, opacity 0`，`stagger .08`，`start:'top 85%'`。

**evidence**
- 星点生成（见 11.8），只生成一次。
- 桌面（`gsap.matchMedia('(min-width:901px)')`）：`#statsPin` 的 pin 时间线——
  ```js
  const proxy = { p: 0 };
  gsap.timeline({ scrollTrigger:{ trigger:'#statsPin', start:'top top', end:'+=120%', pin:true, scrub:1 } })
    .to(proxy, { p:1, ease:'none', onUpdate: () => setCounters(proxy.p) }, 0)
    .fromTo('#herd', { yPercent:75 }, { yPercent:6, ease:'none', duration:1 }, 0);
  ```
- 移动（`max-width:900px`）：卡片 `y 30, opacity 0`，`stagger .08`，`start:'top 85%'`；计数器在 `.cards` 触达 `top 80%` 时 `0→1`，`2s power2.out`；`#herd` `yPercent 40→0`，`scrub`。
- 注意：`#statsPin` 在隐藏视图里创建会算错位置，所以只能在 `setupView` 被调用后创建，且离开时必须 `revert`。

**about**
- 时间线逐条从 `y 20, opacity 0` 进场，`stagger .1`。
- 技术栈 chips 轻微上浮。

### 11.7 手风琴

```js
const track = root.querySelector('#track');
if (track) {
  const panels = [...track.querySelectorAll('.panel')];
  const activate = p => panels.forEach(x => {
    const on = x === p;
    x.classList.toggle('is-active', on);
    x.setAttribute('aria-selected', on);
    x.tabIndex = on ? 0 : -1;
  });
  panels.forEach((p, i) => {
    p.addEventListener('click', () => activate(p));
    p.addEventListener('focus', () => activate(p));
    if (matchMedia('(hover:hover) and (min-width:761px)').matches) {
      p.addEventListener('mouseenter', () => activate(p));
    }
    p.addEventListener('keydown', e => {
      if (['ArrowRight','ArrowLeft','Home','End'].includes(e.key)) {
        e.preventDefault();
        const idx = e.key === 'End' ? panels.length - 1 : e.key === 'Home' ? 0
                  : (i + (e.key === 'ArrowRight' ? 1 : -1) + panels.length) % panels.length;
        panels[idx].focus();
      }
    });
  });
}
```

- 首个面板在 HTML 里就带 `.is-active`，避免首帧三格全关。
- 移动端不给 `mouseenter` 绑定；CSS 里已经让三格全展开，互不干扰。
- **只绑定一次**：`setupView` 每次进入能力页都会执行，监听器必须用 `track.dataset.bound` 防重复，或改成在 `#track` 上做事件委托。否则来回切页会叠加多份监听，表现为一次悬停触发多轮切换。

### 11.8 生成元素

- `#heroGlass`：按第 6.1 节的坐标表写入 `.glass`，`width/height` 按中部/外围规则，`aspect-ratio:1`；每个加随机 `--i` 用于呼吸动画。
- `.sq-field[data-count]`：每个 46×46 的 `.grid-sq`，`left = col*48-10px`、`top = row*48+6px`（`col` 0~29、`row` 0~5，随机）；GSAP `opacity 0→1`，`yoyo`，`repeat:-1`，`duration 1.2`，`delay 0~4`，`repeatDelay 0~3`。`reduce` 时直接 `opacity:.35` 静态。
- 星点：64 个 `.star`，`left/top` 随机 0~100%，尺寸 1~2.5px，`animation-delay` 0~4s。
- 萤火：18 个 `.firefly`，`--dx` 取 -80~80px，`--dur` 9~18s，`animation-delay` 为负 0~15s，尺寸 6~12px，`left` 随机 0~100%。
- 所有生成都做上限保护（例如视口宽度 < 760 时星点减半），避免移动端掉帧。

### 11.9 计数器

```js
function setCounters(p) {
  document.querySelectorAll('#statsPin .stat-card').forEach(card => {
    const b = card.querySelector('b');
    const to = +card.dataset.to || 0;
    const dec = +card.dataset.dec || 0;
    const suf = card.dataset.suf || '';
    b.textContent = (to * p).toFixed(dec) + suf;
  });
}
```

- 首次进入视图时 `p=0`，并立即写一次 `setCounters(0)`，避免残留上一轮的数字。
- 文案里已经带空格（如 `" 类"`），中文数字与单位之间保留细空隙。

### 11.10 表单

- 同一套函数服务两个表单（首页 CTA、关于页联系），用 `form.closest('.lead-form')` 或传入表单节点，不依赖重复 id。
- 校验、提交中、成功、错误四种状态都要有视觉与 `aria-live` 文本；错误文案见 6.4。

### 11.11 降级与异常

- `if (!hasGsap) { document.body.classList.add('no-anim');
  document.documentElement.style.setProperty('--anim','0'); }`，CSS 用 `.no-anim .w{opacity:1!important;transform:none!important;filter:none!important}` 兜底，任何从 `opacity:0` 起步的动画都要能被这个类覆盖。
- 所有 `scrollTrigger` 外层判空；Lenis 不存在时用原生滚动。
- 控制台不允许出现未捕获错误（包括 `ScrollTrigger` 未加载时调用 `refresh`）。

---

## 12. 响应式

- `@media (max-width:900px)`：导航 gap 收窄；能力卡两列；卡片高度 120；`#statsPin` 取消 pin、`min-height:100vh;padding:10vh 16px 12vh`；`#band` 隐藏；`#herd` 贴底。
- `@media (max-width:760px)`：
  - 首页 hero `100svh`、`min-height:560px`；`.hero-copy{top:19%;gap:10px;padding:0 14px}`，`.hero-title{font-size:clamp(30px,8.6vw,40px)}`，`.hero-sub{font-size:12.5px;max-width:330px}`，按钮保持一行；`.hero-media{height:66%;mask:transparent 0 → #000 14%}`；HUD 只留两个角标；云更小（左 `70vw`、`top:6%`；右 `66vw`、`top:10%`）；导航紧凑。
  - 手风琴退化为堆叠列表（见 7.2）；页面高度 auto。
  - 数据页表格允许横向滚动包裹（`overflow-x:auto`），星点减半。
  - CTA `padding:60px 0 0`；夜空场景 `height:92vh;min-height:620px`；卡片 `margin-top:-18vh` 叠在夜空上；表单竖排（input 与按钮各占一行，按钮充满）。
  - 页脚单列居中。
- `@media (prefers-reduced-motion: reduce)`：`.drift-a,.drift-b,.firefly,.star,.hud-rec i{animation:none!important}`；不生成萤火/星点；跳过开场与 pin。

---

## 13. 验收清单（交付前逐条在浏览器里点一遍）

**页面切换**
1. 打开页面 → 默认 `#/home`；地址栏为空时自动补成 `#/home`（不刷新）。
2. 依次点击 首页 / 能力 / 数据与边界 / 关于：地址栏 hash 变化、内容切换、导航高亮同步、滚动回到顶部。
3. 浏览器后退 3 次、前进 3 次：页面与 URL 一致，无空白、无重叠。
4. 直接打开 `index.html#/evidence`：星夜页正确显示，可继续切换。
5. 快速连点导航 10 次：始终 `.view.is-active` 恰好 1 个，无错位。
6. 控制台执行 `document.querySelectorAll('.view.is-active').length` 恒为 `1`；来回切换 5 次后 `ScrollTrigger.getAll().length` 不持续增长（无泄漏）。
7. 导航「预约演示」：切到首页并滚动到 CTA 表单。
8. 页脚四个链接、社交图标、回到顶部均可用。

**动效与场景**
9. 首屏：模糊牧场底色 → 白页 90% 放大到 100%、圆角归零；导航与标题词从模糊中出现；两团云从两侧进入；玻璃方块闪烁。
10. 首页：hero 视差、牛群缓慢移动、识别框跟随、扫描线；滚动到价值卡与流程条时逐块淡入。
11. 能力页：三格手风琴，悬停任意面板仅该格展开，其余格被裁切成窄条；数字颜色依次为橄榄/绿/黄绿；键盘 `←/→/Home/End` 可切换。
12. 数据页（≥901px）：pin 生效，滚动时 4 个数字从 0 涨到 4 / 26 / 100 / 100，牛群剪影从卡片后方升起，磨砂带在数据来源上方。
13. 数据页（≤900px）：无 pin、数字一次性涨完；页面不抖。
14. 首页 CTA：夜空视差、萤火下落、卡片模糊淡入；表单空提交、错误邮箱、正确邮箱三种状态都符合 6.4。
15. 页脚：滚到页脚时三点弹跳 → 合并 → 点 1 变大 → 山形线画出 → 圆环收尾。
16. 刷新页面后滚动到页脚：动画只播放一次，不重复闪烁。

**布局与降级**
17. 360 / 390 / 768 / 1024 / 1440 五个宽度：无横向滚动条（`document.documentElement.scrollWidth <= innerWidth`）。
18. 手机宽度下 HUD、页面、表单、表格都可读，按钮可点。
19. DevTools 断开网络后重新打开：正文可见、四页可切、手风琴可点、表单校验可跑（仅动画与字体降级）。
20. 系统开启「减少动态效果」：无无限动画、无 pin、无粒子。

**内容**
21. 全页搜索不得出现：`petalyx`、`Petalyx`、樱花、`lorem`、`TODO`、`href="#"`。
22. 全页不得出现「诊断 / 疾病预测 / 存栏真值 / 100% 准确 / 已服务 N 家」等越界表述（见第 2 节）。
23. 每个数字旁都有「开发样例」或等价限定语。

---

## 14. 输出要求

1. 只输出完整的 `index.html`（含内联 CSS 与 JS），不要解释、不要分文件、不要注释掉的备用方案。
2. 四个视图的内容都要写满，不允许任何 `<div class="placeholder">` 或空 section。
3. 页面必须能直接双击打开（`file://` 协议下 hash 路由正常工作）。
4. 交付前自检一遍第 13 节清单；不确定的项目宁可删动效，也不要留假交互。

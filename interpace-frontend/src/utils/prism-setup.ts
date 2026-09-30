/**
 * 把 Prism 挂到全局——这是 prismjs 语言组件正常工作的前提。
 *
 * 背景（一个只在生产构建里出现的坑）：
 * `prismjs/components/prism-*.js` 这些语言包是给 `<script>` 直接引入设计的，
 * 它们引用的是**全局变量** `Prism`，而不是 `import` 进来的那个模块。
 *
 * Prism 核心其实是会挂全局的，但它写的是：
 *
 * ```js
 * typeof global !== 'undefined' && (global.Prism = Prism)
 * ```
 *
 * 浏览器里没有 `global`（那是 Node 的东西），所以**这句永远不执行**。
 * 打包后语言包先跑、全局还不存在，于是抛：
 *
 * ```
 * ReferenceError: Prism is not defined
 * ```
 *
 * 开发模式看不到这个错，因为 Vite 的 CJS 互操作会补上 `global`——
 * **只有生产构建才会暴露**（真机上就是这么炸的）。
 *
 * 所以这里自己把全局挂上，并且**必须保证本模块先于所有 `prismjs/components/*` 求值**：
 * ESM 里同一个模块内的依赖按 import 书写顺序求值，所以在 markdownUtil 里
 * 把 `import './prism-setup'` 放在语言包之前即可。
 */

import Prism from 'prismjs'

;(globalThis as unknown as { Prism: typeof Prism }).Prism = Prism

export default Prism

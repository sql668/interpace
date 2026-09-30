<!--
  首页（落地页）：介绍项目、亮点、架构与演示环境限制。

  设计说明（为什么长这样）：
  - **配色沿用产品既有色**：主蓝 #4385f1、品牌暖橙 #f59a1b、纸白 #fbf8f3 都来自
    登录页与房间页，首页不该是另一套视觉。深墨 #16232f 只用于 hero 与记忆区块。
  - **标题用宋体**：这个产品的产物是简历、复盘、评价这类"书面文件"，宋体自带那种正式感，
    而且系统自带、不引入字体依赖。正文仍是全站的黑体。
  - **数字与标记用等宽**：L1/L2/L3、配额数字这类"数据"用等宽字体，一眼与文案区分开。
  - **签名元素是"记忆三层"剖面图**：这是产品最核心的差异点，也是本页最该被记住的东西。
  - **动效只做一处**：hero 的对话卡片逐行出现，呼应产品里的流式回答；其余地方不动，
    `prefers-reduced-motion` 下全部静态。

  演示环境的限制**不写死**，读后端 `/config/runtime`：配置改了页面还写着旧数字，那是在骗人。
-->
<template>
  <div class="home">
    <header class="topbar">
      <div class="wrap topbar__inner">
        <a class="brand" href="#top">
          <span class="brand__mark">面途</span>
          <span class="brand__sub">InterPace</span>
        </a>
        <nav class="topbar__nav">
          <a href="#features">功能</a>
          <a href="#memory">记忆</a>
          <a href="#architecture">架构</a>
          <a href="#demo">演示环境</a>
        </nav>
        <el-button class="topbar__cta" type="primary" @click="goToApp">
          {{ hasToken ? '回到工作台' : '开始练习' }}
        </el-button>
      </div>
    </header>

    <main id="top">
      <!-- Hero：左边说清"这是什么"，右边直接给出产品的产物（一场问答 + 复盘结论） -->
      <section class="hero">
        <div class="wrap hero__inner">
          <div class="hero__copy">
            <p class="eyebrow">AI 模拟面试 · 自动复盘</p>
            <h1 class="hero__title">把面试<br />练成肌肉记忆</h1>
            <p class="hero__lead">
              面途是陪你练面试的 AI：像面试官一样追问，像教练一样复盘，
              并且记得住你——你的项目、薄弱点、反复犯的表达问题都会沉淀成画像，
              让下一次回答比上一次更贴着你。
            </p>
            <div class="hero__actions">
              <el-button class="hero__btn" type="primary" size="large" @click="goToApp">
                {{ hasToken ? '回到工作台' : '进入演示环境' }}
              </el-button>
              <a class="hero__link" href="#memory">看看它怎么记住你 →</a>
            </div>
            <p v-if="bannerText" class="hero__banner">{{ bannerText }}</p>
          </div>

          <figure class="transcript" :class="{ 'transcript--played': heroPlayed }">
            <figcaption class="transcript__caption">
              <span class="mono">模拟面试 · 后端岗</span>
              <span class="transcript__live">进行中</span>
            </figcaption>
            <ol class="transcript__list">
              <li class="transcript__row">
                <span class="who">面试官</span>
                <p>你说做过订单系统，那笔订单超时未支付自动关闭，是怎么实现的？</p>
              </li>
              <li class="transcript__row">
                <span class="who">候选人</span>
                <p>用定时任务扫超时订单，然后关单。</p>
              </li>
              <li class="transcript__row transcript__row--probe">
                <span class="who">面试官</span>
                <p>单机定时任务在集群里会重复关单吗？你怎么保证只关一次？</p>
              </li>
              <li class="transcript__row transcript__row--note">
                <span class="who">复盘</span>
                <p>
                  能讲清实现，但没主动提到并发与幂等。
                  <span class="tag tag--weak">并发编程 · 待加强</span>
                  <span class="tag tag--weak">幂等设计 · 待加强</span>
                  <span class="tag tag--good">项目细节 · 清晰</span>
                </p>
              </li>
            </ol>
          </figure>
        </div>
      </section>

      <!-- 练面试难在哪：三个痛点各对应一个能力。没有先后关系，所以不编号 -->
      <section class="section">
        <div class="wrap">
          <h2 class="section__title">练面试最难的地方，是没人给你追问</h2>
          <div class="grid grid--3">
            <article v-for="item in problems" :key="item.title" class="card card--plain">
              <h3 class="card__title">{{ item.title }}</h3>
              <p class="card__body">{{ item.body }}</p>
              <p class="card__fix">{{ item.fix }}</p>
            </article>
          </div>
        </div>
      </section>

      <section id="features" class="section section--tint">
        <div class="wrap">
          <h2 class="section__title">两个房间，四种练法</h2>
          <p class="section__lead">
            左边是学习室，右边是面试间。每个房间里的「模式」决定了这一轮由哪个 Agent 回答你——
            选错模式不会崩，只是回答的侧重点不同。
          </p>
          <div class="grid grid--2">
            <article v-for="room in rooms" :key="room.name" class="room">
              <h3 class="room__name">{{ room.name }}</h3>
              <p class="room__desc">{{ room.desc }}</p>
              <ul class="room__modes">
                <li v-for="mode in room.modes" :key="mode.label">
                  <span class="dot" :style="{ background: mode.color }" />
                  <div>
                    <p class="mode__label">{{ mode.label }}</p>
                    <p class="mode__body">{{ mode.body }}</p>
                  </div>
                </li>
              </ul>
            </article>
          </div>
          <p class="section__foot">
            另外还有<strong>笔记本</strong>：把任何一轮对话一键存成笔记，它会进入检索索引，
            以后你说"上次那个…"它能翻出来。
          </p>
        </div>
      </section>

      <!-- 签名元素：记忆三层剖面 -->
      <section id="memory" class="section section--ink">
        <div class="wrap">
          <h2 class="section__title section__title--light">它记住你什么，记在哪，什么时候用</h2>
          <p class="section__lead section__lead--light">
            三层记忆。借鉴 Hermes 的分层思路，但每个人的记忆完全隔离——
            你的画像不会影响任何其他人。
          </p>

          <ol class="layers">
            <li v-for="layer in layers" :key="layer.code" class="layer">
              <div class="layer__code mono">{{ layer.code }}</div>
              <div class="layer__main">
                <h3 class="layer__title">{{ layer.title }}</h3>
                <p class="layer__body">{{ layer.body }}</p>
                <dl class="layer__meta">
                  <div><dt>记住</dt><dd>{{ layer.what }}</dd></div>
                  <div><dt>存在</dt><dd class="mono">{{ layer.where }}</dd></div>
                  <div><dt>触发</dt><dd>{{ layer.when }}</dd></div>
                </dl>
              </div>
            </li>
          </ol>

          <div class="rules">
            <h3 class="rules__title">写入不是"模型说了算"</h3>
            <ul class="rules__list">
              <li v-for="rule in memoryRules" :key="rule">{{ rule }}</li>
            </ul>
          </div>
        </div>
      </section>

      <!-- 自主进化：这几步真的有先后关系，所以用序号 -->
      <section class="section">
        <div class="wrap">
          <h2 class="section__title">它不是"用一次忘一次"——每一轮都在变准</h2>
          <ol class="loop">
            <li v-for="(step, index) in evolution" :key="step.title" class="loop__step">
              <span class="loop__index mono">{{ index + 1 }}</span>
              <h3 class="loop__title">{{ step.title }}</h3>
              <p class="loop__body">{{ step.body }}</p>
            </li>
          </ol>
          <p class="section__foot">
            所以用久了会出现这种事：第一周它给你一份"标准答案"，
            第三周它开始挑你上次犯过的那个毛病——因为它手上有你的历史证据。
          </p>
        </div>
      </section>

      <section id="architecture" class="section section--tint">
        <div class="wrap">
          <h2 class="section__title">怎么搭的</h2>
          <p class="section__lead">
            后端按「路由 / 校验 / 业务 / 数据」四层拆开，智能体编排用 LangGraph，
            整站跑在一台 2 核 2G 的轻量云服务器上。
          </p>

          <div class="arch">
            <div v-for="group in architecture" :key="group.layer" class="arch__row">
              <p class="arch__layer mono">{{ group.layer }}</p>
              <div class="arch__items">
                <span v-for="item in group.items" :key="item" class="chip">{{ item }}</span>
              </div>
              <p class="arch__note">{{ group.note }}</p>
            </div>
          </div>

          <div class="grid grid--3 arch__points">
            <article v-for="point in designPoints" :key="point.title" class="card card--plain">
              <h3 class="card__title">{{ point.title }}</h3>
              <p class="card__body">{{ point.body }}</p>
            </article>
          </div>
        </div>
      </section>

      <section id="demo" class="section">
        <div class="wrap">
          <h2 class="section__title">演示环境能试到什么</h2>
          <p class="section__lead">
            演示环境是真跑的，调用的是真模型，所以要有节制的限制——
            下面这些数字来自后端配置，改配置页面就会跟着变。
          </p>

          <div v-if="limitItems.length" class="limits">
            <div v-for="item in limitItems" :key="item.label" class="limits__item">
              <p class="limits__value mono">{{ item.value }}</p>
              <p class="limits__label">{{ item.label }}</p>
              <p class="limits__hint">{{ item.hint }}</p>
            </div>
          </div>
          <p v-else class="limits__none">当前环境没有开启配额限制。</p>

          <ul class="demo__notes">
            <li v-if="!features.voice_interview">
              <strong>语音面试没有开放</strong>：它是 ASR 按时长 + TTS 按字符的双计费链路，
              演示环境关掉了入口，后端也会拒绝直连。
            </li>
            <li v-if="!features.file_upload">
              <strong>附件上传没有开放</strong>：PDF 解析出的全文会整段进上下文，
              一次能顶几十轮对话。
            </li>
            <li v-if="interviewMaxMinutes > 0">
              单场模拟面试最长 <strong>{{ interviewMaxMinutes }} 分钟</strong>，到点自动结束
              （语音由服务端掐断，文字不再回答新问题）。
            </li>
            <li>数据每天会重置，请不要上传真实简历等敏感信息。</li>
          </ul>
        </div>
      </section>
    </main>

    <footer class="footer">
      <div class="wrap footer__inner">
        <p>面途 InterPace · AI 模拟面试与自动复盘</p>
        <el-button link type="primary" @click="goToApp">进入工作台</el-button>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getAccessToken } from '@/api/token'
import { useRuntimeConfig } from '@/composables/useRuntimeConfig'

const router = useRouter()
const hasToken = computed(() => Boolean(getAccessToken()))

const { runtimeConfig, ensureRuntimeConfig } = useRuntimeConfig()
const features = computed(
  () => runtimeConfig.value?.features ?? { voice_interview: true, file_upload: true }
)
const interviewMaxMinutes = computed(() => runtimeConfig.value?.interview_max_minutes ?? 0)
const bannerText = computed(() => runtimeConfig.value?.notice.banner_text ?? '')

// hero 卡片的逐行出现：只在加载后播一次，不做滚动动画。
const heroPlayed = ref(false)

const goToApp = () => {
  router.push(hasToken.value ? '/interview-room' : '/login')
}

onMounted(async () => {
  await ensureRuntimeConfig()
  // 延迟一帧再置位，保证 CSS 过渡真的跑起来（Vue 会先渲染初始态）。
  requestAnimationFrame(() => {
    heroPlayed.value = true
  })
})

/** 痛点 → 对应能力。 */
const problems = [
  {
    title: '对着镜子背，没人追问',
    body: '自己准备时，答不上来的地方会不自觉跳过去，越练越顺的只有本来就会的那部分。',
    fix: '面试官 Agent 会顺着你的回答往下追：你提到"定时任务"，它追问集群里怎么防止重复关单。'
  },
  {
    title: '不知道差在哪',
    body: '"感觉答得还行"是最常见也最没用的一句反馈，它没法告诉你下一步改什么。',
    fix: '复盘给出整体总结、薄弱知识点与可执行的改进建议，还能针对薄弱点直接开讲。'
  },
  {
    title: '换个 AI 问，它不认识你',
    body: '每次都要重新自我介绍，同一类问题反复被指出，聊完就忘。',
    fix: '三层记忆把能力、薄弱点、表达习惯沉淀下来，并在之后的回答里带上。'
  }
]

/** 房间与模式。颜色沿用产品里已有的模式色。 */
const rooms = [
  {
    name: '学习室',
    desc: '把不会的补上，再测一遍有没有真会。',
    modes: [
      {
        label: '知识精讲',
        color: '#4385f1',
        body: '把一个知识点讲透，可以接着追问、也可以转成语音播客。'
      },
      {
        label: '刷题评测',
        color: '#f59a1b',
        body: '按岗位出卷，答完自动评分，薄弱点直接写进画像。'
      }
    ]
  },
  {
    name: '面试间',
    desc: '完整走一遍：改简历 → 模拟面试 → 复盘。',
    modes: [
      {
        label: '简历优化',
        color: '#2f7a56',
        body: '解析简历并给出改法、导出 Word；抽到的信息要你确认才写进画像。'
      },
      {
        label: '模拟面试 + 复盘',
        color: '#e06262',
        body: '一问一答或语音对话，结束后生成复盘，并把薄弱点合并进长期记忆。'
      }
    ]
  }
]

/** 三层记忆（本页的签名元素）。 */
const layers = [
  {
    code: 'L1',
    title: '明细 · 你的能力账本',
    body:
      '每一次作答、每一份简历、每一次复盘都会变成具体记录：掌握度 82 的技能、' +
      '被证据命中 4 次的薄弱点、某类表达问题出现的次数。',
    what: '技能 · 薄弱点 · 答题方法',
    where: 'user_memories',
    when: '每次回答前，挑与当前岗位相关的注入'
  },
  {
    code: 'L2',
    title: '方法 · 反复出现的问题沉淀成套',
    body:
      '如果"讲项目没给数字"出现三次，它就不再是三条备注，而是一条稳定的方法论；' +
      '再遇到同类问题会复用同一条说法，越用越准。',
    what: '答题方法 · 反复出现的表达问题',
    where: 'user_memories / method',
    when: '只在面试与复盘场景注入'
  },
  {
    code: 'L3',
    title: '检索 · 翻得出你说过的原话',
    body:
      '历史对话、笔记、复盘都建了全文索引。当你说"上次那个缓存穿透的方案"，' +
      '它把原文翻出来接着聊，而不是重新问一遍。',
    what: '对话 · 笔记 · 复盘的原文',
    where: 'search_documents',
    when: '只在你话里出现回溯指代时才查'
  }
]

const memoryRules = [
  '行为证据 > 自述与简历 > 模型推断：弱来源不能覆盖强来源，强来源可以纠正弱来源。',
  '模型推断出的画像先落成"待确认"，你点了确认才会生效。',
  '每一类都有容量上限，满了自动合并相近条目，而不是无限堆积。',
  '每次改动都留变更日志，你能在「我的画像」里看到它记住了什么，也能改、能删。',
  '记忆按用户隔离：别人的画像不会进入你的提示词，你的也不会流出去。'
]

/** 自主进化的闭环。这几步确有先后顺序，所以用序号。 */
const evolution = [
  { title: '你答一轮', body: '出题评分、面试问答、简历优化，每个动作都会留下证据。' },
  { title: '抽取候选', body: '从这一轮里抽出"值得长期记住"的结论，而不是把整段对话塞进画像。' },
  {
    title: '合并与加权',
    body: '同一件事再次出现时累加证据、按来源权重重算掌握度，而不是覆盖成新的一条。'
  },
  {
    title: '超限则整合',
    body: '某类条目超过上限时触发一次整合：合并相近项、淘汰最不重要的，保持画像干净。'
  },
  {
    title: '下一轮用上',
    body: '下一次回答会把相关记忆注入提示词——你会感到它"记得你"，而不是从零开始。'
  }
]

const architecture = [
  {
    layer: '前端',
    items: ['Vue 3', 'Vite', 'TypeScript', 'Pinia', 'Element Plus'],
    note: '路由级懒加载，笔记页的大依赖不占首屏。'
  },
  {
    layer: '接口',
    items: ['FastAPI', 'REST /api/v1', 'SSE 流式', 'WebSocket'],
    note: '路由 / 校验 / 业务 / 数据四层分离，业务逻辑不写在路由里。'
  },
  {
    layer: '智能体',
    items: ['LangGraph', 'LangChain', '对话图', '记忆抽取状态图'],
    note: '按模式路由到不同 Agent 与提示词；记忆的"超限整合"用状态图的分支表达。'
  },
  {
    layer: '数据',
    items: ['MySQL', 'Redis', 'MinIO', 'Alembic'],
    note: '中文检索用 MySQL 全文索引 + ngram 分词；表结构变更全部走迁移。'
  },
  {
    layer: '语音',
    items: ['火山引擎 ASR', '火山引擎 TTS', '双向流式'],
    note: 'Key 只留在后端；音频边说边传，面试官的话边合成边播。'
  }
]

const designPoints = [
  {
    title: '流式是默认，不是加分项',
    body: '回答逐字返回，随时可以停止；停止后已生成的内容照样落库，不会丢。'
  },
  {
    title: '成本是可观测的',
    body: '每次模型调用都记一笔真实用量（含推理 token），配额与熔断都基于这份账本。'
  },
  {
    title: '能在小机器上跑',
    body: '目标机器 2 核 2G：单 worker、镜像在本地构建、内存留足余量。'
  }
]

/** 演示环境限制：数字全部来自后端配置，不在页面里写死。 */
const limitItems = computed(() => {
  const value = runtimeConfig.value?.limits
  if (!value) return []
  return [
    {
      value: `${(value.tokens_per_ip / 10000).toLocaleString('zh-CN')} 万`,
      label: '每个 IP 累计可用的 token',
      hint: '输入、输出、推理 token 都算在内'
    },
    {
      value: `${value.turns_per_day} 轮`,
      label: '每天对话上限',
      hint: `单个会话最多 ${value.max_turns_per_session} 轮`
    },
    {
      value: `${value.quizzes_per_day} 次`,
      label: '每天出题评分',
      hint: `复盘 ${value.evaluations_per_day} 次 · 语音 ${value.voice_minutes_per_day} 分钟`
    },
    {
      value: `${value.max_sessions} / ${value.max_notes}`,
      label: '账号可建的会话 / 笔记数',
      hint: '超出后删掉旧的即可继续'
    }
  ]
})
</script>

<style scoped lang="scss">
/* ---- 设计令牌 ---- */
$ink: #16232f;      /* hero 与记忆区块的深底 */
$ink-soft: #26394a; /* 记忆区块，比 hero 浅一档 */
$paper: #fbf8f3;    /* 页面底色，与登录页一致 */
$tint: #f1f4f9;     /* 交替区块底色 */
$blue: #4385f1;     /* 主色，与房间页一致 */
$amber: #f59a1b;    /* 品牌暖色，与登录页一致 */
$green: #2f7a56;    /* 语义：强项 */
$coral: #e06262;    /* 语义：弱项 */
$slate: #6b7684;    /* 次级文字 */
$line: #dfe5ee;     /* 分隔线 */

$display: "Songti SC", "SimSun", Georgia, serif;
$body: "PingFang SC", "Microsoft YaHei", sans-serif;
$mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace;

.mono {
  font-family: $mono;
  font-variant-numeric: tabular-nums;
}

.wrap {
  width: 100%;
  max-width: 1120px;
  margin: 0 auto;
  padding: 0 32px;
}

.home {
  min-height: 100vh;
  background: $paper;
  color: #2f3642;
  font-family: $body;
}

/* ---- 顶栏 ---- */
.topbar {
  position: sticky;
  top: 0;
  z-index: 10;
  background: rgba(251, 248, 243, 0.94);
  border-bottom: 1px solid $line;
}

.topbar__inner {
  display: flex;
  align-items: center;
  gap: 32px;
  height: 68px;
}

.brand {
  display: flex;
  align-items: baseline;
  gap: 8px;
  text-decoration: none;
  color: inherit;
}

.brand__mark {
  font-family: $display;
  font-size: 22px;
  letter-spacing: 2px;
}

.brand__sub {
  font-family: $mono;
  font-size: 12px;
  color: $slate;
}

.topbar__nav {
  display: flex;
  gap: 24px;
  margin-left: auto;

  a {
    color: $slate;
    text-decoration: none;
    font-size: 14px;
    padding: 6px 2px;
    border-bottom: 2px solid transparent;
  }

  a:hover,
  a:focus-visible {
    color: $ink;
    border-bottom-color: $amber;
    outline: none;
  }
}

.topbar__cta {
  border-radius: 999px;
}

/* ---- Hero ---- */
.hero {
  background: $ink;
  color: #eef3f8;
  padding: 72px 0 80px;
}

.hero__inner {
  display: flex;
  gap: 56px;
  align-items: flex-start;
}

.hero__copy {
  flex: 1 1 460px;
  min-width: 0;
}

.eyebrow {
  font-family: $mono;
  font-size: 12px;
  letter-spacing: 3px;
  color: $amber;
  margin: 0 0 20px;
}

.hero__title {
  font-family: $display;
  font-size: 58px;
  line-height: 1.14;
  letter-spacing: 4px;
  font-weight: 600;
  margin: 0 0 24px;
}

.hero__lead {
  font-size: 16px;
  line-height: 1.9;
  color: #b9c6d2;
  max-width: 30em;
  margin: 0 0 32px;
}

.hero__actions {
  display: flex;
  align-items: center;
  gap: 20px;
}

.hero__btn {
  border-radius: 999px;
  padding: 0 28px;
}

.hero__link {
  color: $amber;
  text-decoration: none;
  font-size: 14px;
}

.hero__link:hover,
.hero__link:focus-visible {
  text-decoration: underline;
}

.hero__banner {
  margin: 24px 0 0;
  font-size: 13px;
  color: #8fa1b2;
}

/* hero 右侧：一场真实的问答 + 复盘结论（产品的产物，而不是抽象插画） */
.transcript {
  flex: 0 0 420px;
  margin: 0;
  background: #1e2f3f;
  border: 1px solid #2d4256;
  border-radius: 14px;
  padding: 20px 22px 22px;
  box-shadow: 0 24px 48px rgba(0, 0, 0, 0.28);
}

.transcript__caption {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: #8fa1b2;
  border-bottom: 1px solid #2d4256;
  padding-bottom: 12px;
  margin-bottom: 16px;
}

.transcript__live {
  color: #9fe0bd;
  background: rgba(47, 122, 86, 0.2);
  border-radius: 999px;
  padding: 2px 10px;
}

.transcript__list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.transcript__row {
  position: relative;
  padding-left: 62px;
  margin-bottom: 16px;
  opacity: 0;
  transform: translateY(6px);
  transition: opacity 0.45s ease, transform 0.45s ease;

  p {
    margin: 0;
    font-size: 14px;
    line-height: 1.7;
    color: #dbe5ee;
  }
}

.transcript--played .transcript__row {
  opacity: 1;
  transform: none;
}

/* 逐行出现，像产品里的流式回答 */
.transcript--played .transcript__row:nth-child(1) { transition-delay: 0.1s; }
.transcript--played .transcript__row:nth-child(2) { transition-delay: 0.7s; }
.transcript--played .transcript__row:nth-child(3) { transition-delay: 1.3s; }
.transcript--played .transcript__row:nth-child(4) { transition-delay: 2s; }

.who {
  position: absolute;
  left: 0;
  top: 1px;
  width: 50px;
  text-align: right;
  font-size: 12px;
  color: #8fa1b2;
}

.transcript__row--probe .who {
  color: $amber;
}

.transcript__row--probe p {
  color: #f4e6cd;
}

.transcript__row--note {
  border-top: 1px dashed #2d4256;
  padding-top: 14px;
  margin-bottom: 0;
}

.transcript__row--note .who {
  color: #7fb0ff;
}

.tag {
  display: inline-block;
  font-size: 12px;
  border-radius: 4px;
  padding: 1px 8px;
  margin: 6px 6px 0 0;
}

.tag--weak {
  color: #ffb4b4;
  background: rgba(224, 98, 98, 0.18);
}

.tag--good {
  color: #9fe0bd;
  background: rgba(47, 122, 86, 0.22);
}

/* ---- 通用区块 ---- */
.section {
  padding: 72px 0;
}

.section--tint {
  background: $tint;
}

.section--ink {
  background: $ink-soft;
  color: #eef3f8;
}

.section__title {
  font-family: $display;
  font-size: 32px;
  letter-spacing: 2px;
  font-weight: 600;
  color: $ink;
  margin: 0 0 16px;
}

.section__title--light {
  color: #eef3f8;
}

.section__lead {
  font-size: 15px;
  line-height: 1.9;
  color: $slate;
  max-width: 46em;
  margin: 0 0 36px;
}

.section__lead--light {
  color: #a9b8c6;
}

.section__foot {
  margin-top: 32px;
  font-size: 14px;
  line-height: 1.8;
  color: $slate;
}

.grid {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
}

.grid--3 > * {
  flex: 1 1 280px;
}

.grid--2 > * {
  flex: 1 1 420px;
}

.card {
  background: #fff;
  border: 1px solid $line;
  border-radius: 12px;
  padding: 24px;
}

/* 无边框卡片：用顶部一条粗线做分隔，比描边更安静 */
.card--plain {
  background: transparent;
  border: none;
  border-top: 3px solid $ink;
  border-radius: 0;
  padding: 20px 0 0;
}

.card__title {
  font-size: 17px;
  color: $ink;
  margin: 0 0 10px;
}

.card__body {
  font-size: 14px;
  line-height: 1.85;
  color: $slate;
  margin: 0 0 12px;
}

.card__fix {
  font-size: 14px;
  line-height: 1.85;
  color: #2f3642;
  margin: 0;
  padding-left: 12px;
  border-left: 2px solid $amber;
}

/* ---- 房间与模式 ---- */
.room {
  background: #fff;
  border: 1px solid $line;
  border-radius: 12px;
  padding: 24px;
}

.room__name {
  font-family: $display;
  font-size: 22px;
  letter-spacing: 1px;
  color: $ink;
  margin: 0 0 6px;
}

.room__desc {
  font-size: 13px;
  color: $slate;
  margin: 0 0 20px;
}

.room__modes {
  list-style: none;
  margin: 0;
  padding: 0;

  li {
    display: flex;
    gap: 12px;
    padding: 14px 0;
    border-top: 1px solid $line;
  }
}

.dot {
  flex: 0 0 auto;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-top: 7px;
}

.mode__label {
  font-size: 15px;
  color: $ink;
  margin: 0 0 4px;
}

.mode__body {
  font-size: 13px;
  line-height: 1.8;
  color: $slate;
  margin: 0;
}

/* ---- 记忆三层（签名元素） ---- */
.layers {
  list-style: none;
  margin: 0;
  padding: 0;
  position: relative;
}

/* 贯穿三层的竖线：让"层"这件事在结构上看得见 */
.layers::before {
  content: "";
  position: absolute;
  left: 61px;
  top: 12px;
  bottom: 12px;
  width: 1px;
  background: linear-gradient(180deg, $amber, rgba(245, 154, 27, 0.15));
}

.layer {
  display: flex;
  gap: 24px;
  padding: 24px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.layer:last-child {
  border-bottom: none;
}

.layer__code {
  flex: 0 0 auto;
  width: 62px;
  height: 28px;
  line-height: 28px;
  text-align: center;
  font-size: 13px;
  color: $ink;
  background: $amber;
  border-radius: 4px;
}

.layer__main {
  flex: 1 1 auto;
  min-width: 0;
  padding-left: 12px;
}

.layer__title {
  font-family: $display;
  font-size: 20px;
  letter-spacing: 1px;
  color: #eef3f8;
  margin: 0 0 10px;
}

.layer__body {
  font-size: 14px;
  line-height: 1.9;
  color: #b9c6d2;
  margin: 0 0 14px;
  max-width: 58em;
}

.layer__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 28px;
  margin: 0;

  div {
    display: flex;
    gap: 8px;
    font-size: 12px;
  }

  dt {
    color: #7d8f9f;
  }

  dd {
    margin: 0;
    color: #cbd8e3;
  }
}

.rules {
  margin-top: 36px;
  padding: 24px 26px;
  background: rgba(255, 255, 255, 0.04);
  border-left: 3px solid $amber;
  border-radius: 0 10px 10px 0;
}

.rules__title {
  font-size: 16px;
  color: #eef3f8;
  margin: 0 0 12px;
}

.rules__list {
  margin: 0;
  padding-left: 20px;
  color: #b9c6d2;
  font-size: 14px;
  line-height: 2;
}

/* ---- 自主进化闭环 ---- */
.loop {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  counter-reset: none;
}

.loop__step {
  flex: 1 1 190px;
  position: relative;
  padding-top: 18px;
  border-top: 2px solid $line;
}

.loop__index {
  display: inline-block;
  font-size: 13px;
  color: $amber;
  margin-bottom: 10px;
}

.loop__title {
  font-size: 16px;
  color: $ink;
  margin: 0 0 8px;
}

.loop__body {
  font-size: 13px;
  line-height: 1.85;
  color: $slate;
  margin: 0;
}

/* ---- 架构 ---- */
.arch {
  border-top: 1px solid $line;
}

.arch__row {
  display: flex;
  align-items: baseline;
  gap: 20px;
  padding: 18px 0;
  border-bottom: 1px solid $line;
}

.arch__layer {
  flex: 0 0 68px;
  font-size: 13px;
  color: $ink;
}

.arch__items {
  flex: 1 1 auto;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.chip {
  font-size: 12px;
  color: #3b4756;
  background: #fff;
  border: 1px solid $line;
  border-radius: 999px;
  padding: 3px 12px;
}

.arch__note {
  flex: 0 0 320px;
  font-size: 13px;
  line-height: 1.8;
  color: $slate;
  margin: 0;
}

.arch__points {
  margin-top: 40px;
}

/* ---- 演示环境限制 ---- */
.limits {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
}

.limits__item {
  flex: 1 1 220px;
  background: #fff;
  border: 1px solid $line;
  border-radius: 12px;
  padding: 22px 24px;
}

.limits__value {
  font-size: 30px;
  color: $ink;
  margin: 0 0 8px;
  letter-spacing: -0.5px;
}

.limits__label {
  font-size: 14px;
  color: #2f3642;
  margin: 0 0 6px;
}

.limits__hint {
  font-size: 12px;
  line-height: 1.7;
  color: $slate;
  margin: 0;
}

.limits__none {
  font-size: 14px;
  color: $slate;
}

.demo__notes {
  margin: 32px 0 0;
  padding-left: 20px;
  font-size: 14px;
  line-height: 2;
  color: $slate;

  strong {
    color: #2f3642;
  }
}

/* ---- 页脚 ---- */
.footer {
  background: $ink;
  color: #8fa1b2;
  padding: 28px 0;
  font-size: 13px;
}

.footer__inner {
  display: flex;
  align-items: center;
  justify-content: space-between;

  p {
    margin: 0;
  }
}

/* ---- 无障碍：尊重系统的"减少动态效果" ---- */
@media (prefers-reduced-motion: reduce) {
  .transcript__row {
    opacity: 1;
    transform: none;
    transition: none;
  }
}
</style>

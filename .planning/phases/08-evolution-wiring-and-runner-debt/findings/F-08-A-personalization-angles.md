# F-08-A — 个性化角度（personalization angles）自底向上推导

**Agent**: A（独立分析，未读任何 SKILL.md / 当前 copy 输出 / rubric 判分）
**输入**: 11 个 real-LLM 请求的 `factor_discovery/messages.jsonl` 中 `message[1].content` 解出的 user_state + target_product + derived_features payload
**目标**: 仅凭原始用户行为数据，推导出 slogan（8–16 字）可挖掘的角度（angle）；不评论现状产物。

> 11 个请求实际只有 9 个不同 user_id（`294379371` 在 stage1_req0 / s2_req7 / s2_req8 各出现一次，分别配 3 个 target product），下文行号沿用 11 行编号但合并描述时会指明。

---

## 1. Per-user 行为指纹表

| 行号 (tag) | user_id | gender·age | region·city_level | register_days · vip · is_svip | 节奏 (click_30d / order_30d / order_90d / coupon_30d / cart_30d) | ASP (purchase_30d / fav_30d) | 设备·时段·星期 | Top-3 distinctive signals (verbatim) | 生命阶段假设 | 消费姿态 | 地域/时间上下文 | 当次 target_product (canonical · 价 · derived 关键位) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| stage1_req0 | 294379371 | 女·31 | 云南省·二线 | 2936·金卡·SVIP | 77/3/15/0/5 | ¥42.3 / ¥0 | iPhone·9h·周三 | (a) `order_goods`: "苏秘37悦阳防晒4件套 SPF50+/PA+++"; (b) `order_goods`: "儿童玩具抽拉式大容量喷水书包戏水滋水呲水枪"; (c) `prefer_brand`: "韩后(rank=1), 真维斯, 阿迪达斯, 都市丽人, 洁柔" | 8 年金卡老用户、31 岁、家有学龄前→小学男童（戏水玩具、儿童洗护、男大童短袖 click） | 价格地板派但偶发跨级（韩流 SPF 套装）；自我护理（文胸×5 加购，面部精华×8 click）和育儿支出并行 | 二线下沉、早晨 9 点上班路上 / 哄娃出门后 | 兰蔻奇迹香水 ¥249（远超出 4.88×，brand mismatch） |
| s2_req1 | 16546825 | 女·40 | 吉林省·二线 | 5024·金卡·SVIP | 792/4/24/1/41 | ¥85.3 / ¥174 | Android·23h·周三 | (a) `prefer_brand`: "图图小象(rank=1), 媛媛公主, 果壳, 唐狮童装, 逸阳, 珂卡芙, 顶瓜瓜"（全部童装）; (b) `addcart_goods`: "AJIDOU耳钉女简约淡水珍珠925银针耳环通勤时尚礼盒饰品"; (c) `order_goods`: "轻薄羽绒服短款女连帽长袖修身显瘦防风保暖柔软舒适百搭外套" | 13.7 年超长老客户、40 岁多娃妈妈、东北家庭主妇/职场妈妈 | fav_brand 91 vs order 4=收藏远超购买（**收藏夹堆积型**），fav_price 174>purchase 85（aspiration>consumption） | 吉林冬季羽绒高频，23 点哄睡后浏览 | 护腰坐垫人体工学 ¥25（远低于、ctr_band=high、cat3 mismatch） |
| s2_req2 | 366618992 | 男·age=0 | 湖北省·四线 | 2382·银卡 | 207/0/3/0/5 | ¥0 / ¥0 | Android·22h·周三 | (a) `order_goods`: "【防风御寒厚款加绒裤】冬季女式直筒休闲裤高腰加绒加厚阔腿裤女"; (b) `prefer_cat3`: "女式T恤(rank=1), 女式套装, 男式T恤, 女式外套, 连衣裙"; (c) `click_brand`: "真维斯(14), 361°(11), 特步(6), 骆驼(5), 3S(5)" | 银卡四线男账号、age 未填、点击/下单几乎全女装→**家庭代理账号**（家中女性使用） | 30 天 0 单 0 收藏价、90 天才 3 单：浏览狂、决策犹豫，明显比价 | 四线城市晚 22 点、运动品牌+真维斯=本地县城商场常客 | 珍珠零感美白防晒乳 ¥39（无基线、popular、brand recent_touched） |
| s2_req3 | 222884073 | 女·39 | 广东省·一线 | 3423·金卡 | 10/0/13/0/0 | ¥0 / ¥0 | Android·21h·周三 | (a) `order_goods`: "【新中式改良汉服旗袍假两件】连衣裙女夏复古立领盘扣时尚印花裙"; (b) `collect_goods`: "就是栀子鎏金白花香调清新留香香水女士持久淡香大牌持久留香"; (c) `addcart_goods`: "【加绒保暖】冬开学季儿童加绒卫衣拜服舒适百搭柔软亲肤外穿" | 9.4 年金卡、39 岁广州/深圳一线妈妈、孩子上学（开学季加绒卫衣） | click_30d=10 极低→**轻浏览高转化型**（一来就下单），香水 collect×3 表示**有意构建香水货架** | 一线晚 21 点（下班后）、新中式审美强 | 浪漫香水套装 ¥49（无基线、cold review、brand mismatch） |
| s2_req4 | 655292256 | 男·age=0 | 广东省·一线 | **83**·银卡 | 360/3/10/0/18 | ¥73.7 / ¥0 | Android·18h·周三 | (a) `register_days=83`（**全样本最新用户**）+ `click_cnt_30d=360`; (b) `seq_search_cat3_48h`: "男式休闲裤(4), 家居拖鞋(1), 男式套装(1), 婴幼裤子(1)"; (c) `addcart_goods`: "情侣卡通洞洞鞋女踩屎感2025夏季新款室内居家软底包头情侣拖鞋男" | **新用户探索期**、广州一线男、下班 18 点 browse、买童鞋（爸爸） | 高 click 低 order=漏斗顶端、首单还未稳定；情侣拖鞋=情侣关系 | 一线城市、下班后地铁通勤购物 | 护腰坐垫 ¥25（远低于、cat3 mismatch、ctr_band high） |
| s2_req5 | 404619739 | 女·45 | 陕西省·二线 | 2080·白金卡·SVIP | **1338**/3/18/1/79 | ¥46.3 / ¥44.5 | iPhone·14h·周三 | (a) `click_brand`: "**红袖(63)**, 海澜之家(5)"（**单品牌独占近半 click**）; (b) `prefer_brand`: "红袖(rank=1), 星期六, 富贵鸟, 蔻斯琦, 老庙, 吉盟珠宝"; (c) `addcart_goods`: "柿柿如意~红玛瑙新中式简约百搭耳扣2026年新款本命马年耳环" | 5.7 年白金 SVIP、45 岁西安/咸阳、本命年（属马）→ 45 岁意味着上一轮属马 33 年前；近本命年仪式感 | 极端品牌死忠（红袖 monomaniac）+ 黄金/玛瑙仪式珠宝；click 1338 远超下单 18 | iPhone 二线下午 14 点（午休/家里） | 护膝薄款空调房 ¥14.1（远低于、ctr_band high） |
| s2_req6 | 214643681 | 男·49 | 贵州省·**五线** | 3456·金卡 | 482/15/17/0/22 | ¥113.7 / ¥75 | Android·13h·周三 | (a) `click_cat3`: "**女休闲鞋(73)**, 运动休闲鞋(5)"（单 cat3 当日 zoom-in）; (b) `order_goods`: "女童短袖T恤2026夏季儿童泡泡袖度假风蝴蝶结打底衫半袖体恤"; (c) `prefer_brand`: "PIYOPIYO, ASK junior, 沫晗依美, 美丽衣橱, 嫒宝时, 优蜜屋, 花田彩, 三彩, 香影" | 9.5 年金卡、49 岁贵州五线父亲、给女儿（女童甜美款）+ 妻子（女休闲鞋、女式风衣）整柜置办 | order_30d/90d=15/17=**88% 集中近 30 天**→季节性 burst 买家；客单 ¥113 是男性下沉买家高水位 | 五线城市、午 13 点（午饭后） | 素颜小粉帽防晒隔离霜 ¥124（持平基线、cold start combo、is_new=1） |
| s2_req7 | 294379371 | (同 stage1_req0) | 同 | 同 | 同 | 同 | 同 | 同 | 同 | 同 | 同 | 兰蔻奇迹香水 ¥249（**与 stage1_req0 同一 product**） |
| s2_req8 | 294379371 | (同 stage1_req0) | 同 | 同 | 同 | 同 | 同 | 同 | 同 | 同 | 同 | 蔻驰女士MINI香水套组 ¥109（远高于 1.57×、brand mismatch、CVR=0.0099 偏低）|
| s2_req9 | 568296523 | 男·age=0 | 山东省·二线 | 957·银卡 | 126/3/3/2/12 | ¥30.3 / ¥0 | iPhone·8h·周三 | (a) `click_brand`: "**巴拉巴拉(71)**, Mini Balabala(11)"（巴拉巴拉品牌族独占）; (b) `order_goods`: "祛斑玫瑰花红花葡萄籽提取物祛黄褐斑保养肌肤内服男女性白"; (c) `order_goods`: "乳清蛋白粉90%增强免疫力中老年人保健品营养补充食品大豆蛋白" | 2.6 年银卡、男（实为家用账号）、有学龄前小孩、关心老人/伴侣保健 | 最低 ASP（¥30）+ coupon×2 + cart×12=**价格敏感+多比较型**；保健品+亲子 T 恤=家庭囤货心智 | 山东二线晨 8 点（送娃上学/上班路上） | 按压式美白去渍牙膏家庭囤货装 ¥56（远高于、**brand aligned + cat3 aligned**） |
| s2_req10 | 140921217 | 女·43 | 湖北省·二线 | 3844·白金卡·SVIP | **2050**/22/81/11/88 | ¥234.4 / ¥226.3 | iPhone·9h·周三 | (a) `prefer_brand`: "Teenie Weenie(rank=1), 尤尼克斯, The North Face, 婷美, MLB"; (b) `seq_search_brand_48h`: "**威克多(2)**"（羽毛球品牌专攻搜索）; (c) `click_goods`: "【镇店爆款】美肌粉膏浓缩型粉底液持久遮瑕不易脱妆奶油肌防水汗"（毛戈平） | 10.5 年白金、43 岁湖北、运动型职场女（羽毛球+ The North Face POLO），爱国货高端美妆（毛戈平） | 全样本最强买家：ASP ¥234、coupon×11、order×22；同时 click 2050=信息饕餮型 | iPhone 二线晨 9 点（通勤） | 艾斯凯矫姿驼背矫正器 ¥48（**远低于** baseline、ctr_band very_high） |

---

## 2. Cross-user 角度目录（25 个 angles）

每条 angle 含：定义 / Evidence（至少 2 用户 + verbatim 字段）/ 1–2 候选 slogan（8–16 字）/ 反面 anti-pattern。

### A. 身份与生命阶段（Identity & life-stage）

#### A1. 长尾老客户的金卡仪式感
- **定义**: `register_days > 2000` + `vip_level ∈ {金卡, 白金卡}`，长期被平台标签化的"自己人"。
- **Evidence**:
  - stage1_req0 / 294379371: `register_days=2936, vip_level=金卡会员, is_svip=1`
  - s2_req10 / 140921217: `register_days=3844, vip_level=白金卡会员, is_svip=1`
  - s2_req6 / 214643681: `register_days=3456, vip_level=金卡会员`
- **Slogan 范例**:
  - "金卡第八年的小确幸"（10 字）
  - "老顾客才识得这一支"（9 字）
- **Anti-pattern**: "百搭好物，香氛新选"——不识别老客户身份。

#### A2. 多娃妈妈的"购物车里都是孩子"
- **定义**: `prefer_cat3` / `addcart_cat3` 头部 5 项中 ≥ 3 项是儿童/婴幼，且女性。
- **Evidence**:
  - s2_req1 / 16546825: `prefer_cat3: 儿童外套/夹克/风衣(rank=1), 儿童T恤/POLO衫(rank=2), 儿童裤子(rank=3), 女士睡衣/家居服(rank=4), 儿童卫衣(rank=5)`
  - stage1_req0 / 294379371: `order_goods: 儿童玩具抽拉式大容量喷水书包戏水滋水呲水枪 …; 1L*2瓶大容量儿童牛奶洗发水沐浴露温和二合一婴幼洗护新生儿`
- **Slogan 范例**:
  - "哄完娃 自己也来一支"（9 字）
  - "购物车里 终于有一件是我的"（11 字）
- **Anti-pattern**: "时尚百搭，香氛之选"——把妈妈当做无负担少女。

#### A3. 代理购物的父亲（女童 & 妻子代购）
- **定义**: gender=男 且 `prefer_cat3` / `order_goods` 大量女童 / 女士品类。
- **Evidence**:
  - s2_req6 / 214643681: `order_goods: 女童短袖T恤2026夏季儿童泡泡袖度假风蝴蝶结打底衫半袖体恤; 女童裤子中大童洋气花边薄款牛仔裤夏季水洗`；`prefer_brand: PIYOPIYO, ASK junior, 沫晗依美`
  - s2_req2 / 366618992: `prefer_cat3: 女式T恤(rank=1), 女式套装, … 女式外套, 连衣裙`；男账号
- **Slogan 范例**:
  - "替她省去挑半天"（7 字）
  - "选对了她也夸你眼光"（9 字）
- **Anti-pattern**: "夏季清爽，男士新选"——把代理父亲当作自购者。

#### A4. 新用户漏斗顶端探索者
- **定义**: `register_days < 200` 且 `click_cnt_30d / register_days > 1`（高强度比价）。
- **Evidence**:
  - s2_req4 / 655292256: `register_days=83`, `click_cnt_30d=360`（日均 4.3 click），`order_cnt_30d=3`
  - （样本中仅此 1 用户；其余 8 个独立用户 `register_days` 均 > 950）
- **Slogan 范例**:
  - "第一次到我家就别走错门"（11 字）
  - "新人这一单 就当见面礼"（10 字）
- **Anti-pattern**: "百搭好物 经典之选"——错失"新人钩子"机会。

#### A5. 中年女性的"还能为自己买一次"
- **定义**: age ∈ [40, 50] + 长期老用户 + 家有娃 + 自买品（饰品/美妆/香氛）。
- **Evidence**:
  - s2_req10 / 140921217: age=43, `click_brand: 毛戈平(13)`（美妆）`+ MO&Co.(16)`（设计师女装）
  - s2_req5 / 404619739: age=45, `addcart_goods: 柿柿如意~红玛瑙新中式简约百搭耳扣2026年新款本命马年耳环`
  - s2_req1 / 16546825: age=40, `collect_goods: S925银锁骨链O字链金色素链百搭简约基础款`
- **Slogan 范例**:
  - "四十岁那点小自私"（8 字）
  - "这一支留给自己"（7 字）
- **Anti-pattern**: "时尚少女 心动之选"——错把熟龄当少女。

### B. 经济姿态（Economic posture）

#### B1. 价格地板派（mass-market 锚点）
- **定义**: `purchase_price_avg_30d < 50` 且仍是金卡/SVIP 老用户。
- **Evidence**:
  - stage1_req0 / 294379371: `purchase_price_avg_30d=42.33`, SVIP
  - s2_req5 / 404619739: `purchase_price_avg_30d=46.33`, 白金 SVIP
  - s2_req9 / 568296523: `purchase_price_avg_30d=30.33`
- **Slogan 范例**:
  - "大牌也敢平价拿下"（8 字）
  - "白金会员的精打细算"（9 字）
- **Anti-pattern**: "品质之选 你值得拥有"——回避了价格诉求。

#### B2. 价格天花板派（premium baseline）
- **定义**: `purchase_price_avg_30d > 150` + `fav_price_avg_30d > 150`。
- **Evidence**:
  - s2_req10 / 140921217: `purchase_price_avg_30d=234.40, fav_price_avg_30d=226.30`
  - （样本中仅此 1 用户达此标——**低 prevalence，1/9 独立用户**）
- **Slogan 范例**:
  - "配得上你那一柜大牌"（9 字）
  - "比平时更值得这一件"（9 字）
- **Anti-pattern**: 用 "实惠特价" / "超值秒杀" 直接劝退。

#### B3. 收藏夹堆积型（aspiration > consumption）
- **定义**: `fav_price_avg_30d` 显著高于 `purchase_price_avg_30d`（≥ 2×），或 `fav_brand_cnt_30d` >> `order_cnt_30d`。
- **Evidence**:
  - s2_req1 / 16546825: `fav_brand_cnt_30d=91, order_cnt_30d=4`; `fav_price_avg_30d=174.0` vs `purchase_price_avg_30d=85.25`
  - s2_req10 / 140921217: `fav_brand_cnt_30d=47, fav_cnt_30d=23` vs `order_cnt_30d=22`（多收多买，但 47 品牌 vs 22 单显示种草未割韭菜）
- **Slogan 范例**:
  - "收藏夹里 该挑这一件了"（10 字）
  - "心愿单的第 91 个 终于到货"（11 字）
- **Anti-pattern**: "新品上市，必入清单"——又给 fav，没有"成交"钩子。

#### B4. 优惠券密集型
- **定义**: `coupon_use_cnt_30d ≥ 3`。
- **Evidence**:
  - s2_req10 / 140921217: `coupon_use_cnt_30d=11`
  - （样本仅 1 例 ≥3——其余多为 0–2。**低 prevalence，1/9**）
- **Slogan 范例**:
  - "用券价比双十一还猛"（9 字）
  - "攒券攒到今天 就为这一件"（11 字）
- **Anti-pattern**: 不强调 "用券"，让 11 张未用券作废。

#### B5. 品牌阶梯跨级跃迁（brand-tier leap）
- **定义**: `derived_features.price_vs_user_baseline_bucket=远超出 / 远高于` 且 `brand_alignment=mismatch`。
- **Evidence**:
  - stage1_req0 / s2_req7 / 294379371: 兰蔻香水 ¥249，`price_vs_user_baseline_ratio=4.8819, bucket=远超出, brand_alignment=mismatch`（vs ¥42 baseline）
  - s2_req8 / 294379371: 蔻驰香水 ¥109，`bucket=远高于, brand_alignment=mismatch`
- **Slogan 范例**:
  - "第一次试国际大牌的味道"（10 字）
  - "你的衣柜该添一支外国香"（10 字）
- **Anti-pattern**: "经典香氛 优雅之选"——回避了"跨级"这一最大叙事张力。

#### B6. 品牌阶梯下沉（brand-tier dive）
- **定义**: 高 ASP 用户买入 `bucket=远低于` 的实用品。
- **Evidence**:
  - s2_req10 / 140921217: 矫姿器 ¥48，`bucket=远低于`（vs ¥234 baseline）
  - s2_req5 / 404619739: 护膝 ¥14.1，`bucket=远低于`（vs ¥46 baseline）
- **Slogan 范例**:
  - "大牌之外 这件也用得上"（9 字）
  - "实用比贵更难得"（7 字）
- **Anti-pattern**: 用"轻奢高级"反向 push，破坏务实心智。

### C. 品牌关系（Brand relationship）

#### C1. 单品牌死忠（monomaniacal devotion）
- **定义**: `click_brand_id_list_topN` 第一名 click 数 ≥ 第二名的 5×，或单品牌 click 占该用户 click_cnt_30d 的 ≥ 30%。
- **Evidence**:
  - s2_req5 / 404619739: `click_brand: 红袖(63), 海澜之家(5)`（红袖 是次品牌 12.6×；占 click_30d=1338 的 4.7%——仍是该品牌族占 prefer_brand rank=1）
  - s2_req9 / 568296523: `click_brand: 巴拉巴拉(71), Mini Balabala(11), 马骑顿(6)`（巴拉巴拉系列占 click_30d=126 的 65%）
- **Slogan 范例**:
  - "红袖之外 还有它撑得住场"（11 字）
  - "比巴拉巴拉更适合上学路"（10 字）（**跨卖**用法）
- **Anti-pattern**: "经典百搭 必入款"——没有借势用户对原品牌的忠诚。

#### C2. 多品牌博物馆型（collector）
- **定义**: `fav_brand_cnt_30d ≥ 40`。
- **Evidence**:
  - s2_req1 / 16546825: `fav_brand_cnt_30d=91`
  - s2_req10 / 140921217: `fav_brand_cnt_30d=47`
- **Slogan 范例**:
  - "你的品牌图鉴又添新页"（9 字）
  - "47 个收藏 再加一个不多"（11 字）
- **Anti-pattern**: 强调"独一无二"——藏家在乎扩充而非排他。

#### C3. 品类×品牌的"族内回购"
- **定义**: `derived_features.cat3_alignment=aligned` + `brand_alignment=aligned`。
- **Evidence**:
  - s2_req9 / 568296523: 牙膏 ¥56，`cat3_alignment=aligned, brand_alignment=aligned, user_typical_brand_level=国内B, brand_level_vs_user_history=same`（同档同品牌延伸）
  - （样本中仅此 1 例两轴双 aligned；**低 prevalence，1/11**）
- **Slogan 范例**:
  - "还是这个味 还是这个牌"（9 字）
  - "用顺手的 再囤一管"（8 字）
- **Anti-pattern**: 推荐"换一种全新体验"——粉碎复购心智。

### D. 时间与地域上下文（Temporal & regional context）

#### D1. 深夜放空浏览者（22:00 后）
- **定义**: `context.hour ∈ {22, 23, 0, 1}` + `click_cnt_30d ≥ 100`。
- **Evidence**:
  - s2_req1 / 16546825: `hour=23, click_cnt_30d=792`
  - s2_req2 / 366618992: `hour=22, click_cnt_30d=207`
- **Slogan 范例**:
  - "睡前最后一眼的种草"（8 字）
  - "哄睡后 给自己的小礼物"（10 字）
- **Anti-pattern**: "清晨第一抹"——时段错位。

#### D2. 早间通勤购物（8–9 点 + iPhone）
- **定义**: `context.hour ∈ {7, 8, 9}` + `device_type=iPhone`。
- **Evidence**:
  - s2_req9 / 568296523: `hour=8, device_type=iPhone`
  - s2_req10 / 140921217: `hour=9, device_type=iPhone`
  - stage1_req0 / 294379371: `hour=9, device_type=iPhone`
- **Slogan 范例**:
  - "上班路上一键下单"（8 字）
  - "到公司就拆这一件"（8 字）
- **Anti-pattern**: "夜深时刻的陪伴"——错位且煽情过头。

#### D3. 午后在家自留时光（13–14 点 + 女）
- **定义**: `context.hour ∈ {13, 14, 15}` + gender=女 + `vip_level=金卡/白金卡`。
- **Evidence**:
  - s2_req5 / 404619739: `hour=14, gender=女, vip_level=白金卡会员`
  - s2_req6 / 214643681: `hour=13`（男，但同时段）
- **Slogan 范例**:
  - "午休那一刻的犒赏"（8 字）
  - "孩子上学后的小清单"（9 字）
- **Anti-pattern**: 强通勤/下班叙事。

#### D4. 区域气候/地域意象
- **定义**: `region_level` 与 target 的气候/季节性需求关联。
- **Evidence**:
  - s2_req1 / 16546825: `region_level=吉林省`；`order_goods: 轻薄羽绒服短款女连帽长袖修身显瘦防风保暖柔软舒适百搭外套`（×2 件）
  - s2_req5 / 404619739: `region_level=陕西省`；`order_goods: 【高级感英伦风显瘦上衣】26春季时尚气质中长款风衣外套`（×2）
  - s2_req6 / 214643681: `region_level=贵州省`；`order_goods: 女童裙子夏中大童水墨晕染挂脖连衣裙女童出游度假风`（贵州夏季短）
- **Slogan 范例**:
  - "北方冬里得这一件"（8 字）（吉林）
  - "西北春风里的一抹挺括"（9 字）（陕西风衣）
- **Anti-pattern**: 通用季节句"四季皆宜" 抹平地域。

#### D5. 季节性 burst 买家
- **定义**: `order_cnt_30d / order_cnt_90d ≥ 0.8`（最近 30 天集中下单）。
- **Evidence**:
  - s2_req6 / 214643681: `order_cnt_30d=15, order_cnt_90d=17`（88%）
  - （样本中显著的就 1 例——**低 prevalence**）
- **Slogan 范例**:
  - "这波集中补齐 还差这一件"（11 字）
  - "夏天这一轮采买的最后一单"（11 字）
- **Anti-pattern**: "慢慢挑 不着急"——错配紧迫感。

### E. 美学身份（Aesthetic identity）

#### E1. 新中式 / 国风审美
- **定义**: order/click/collect 出现 旗袍 / 汉服 / 盘扣 / 新中式 / 国风提花 / 玛瑙 / 本命 等词。
- **Evidence**:
  - s2_req3 / 222884073: `order_goods: 【新中式改良汉服旗袍假两件】连衣裙女夏复古立领盘扣时尚印花裙`
  - s2_req5 / 404619739: `click_goods: 2026夏季女装国风暗纹提花不对称斜襟盘扣圆领套头上衣`; `addcart: 柿柿如意~红玛瑙新中式简约百搭耳扣2026年新款本命马年耳环`
- **Slogan 范例**:
  - "再添一抹东方调"（7 字）
  - "盘扣之外 还有这一抹"（9 字）
- **Anti-pattern**: 强欧式调"凡尔赛优雅 法式浪漫" 错位。

#### E2. 多巴胺 / 撞色 / 印花趣味
- **定义**: order/click 词出现 多巴胺 / 撞色 / 趣味 / 印花标语。
- **Evidence**:
  - s2_req10 / 140921217: `order_goods: 迷幻泰迪熊印花短袖宽松T恤女装; 趣味小鹿标语复古撞色边T恤女装`
  - s2_req3 / 222884073: `click_goods: 【多巴胺穿搭】春秋新法式印花V领衬衫雪纺七分袖遮肉衬衣女上衣`
- **Slogan 范例**:
  - "多巴胺式的小欢喜"（8 字）
  - "撞色那一刻的快乐"（8 字）
- **Anti-pattern**: "经典纯色 沉稳之选"——压制其表达欲。

#### E3. 运动 / 球类 / 户外 tech 身份
- **定义**: `prefer_brand` 含运动专业品牌（尤尼克斯 / The North Face / 李宁 / 安踏专业线）或 `seq_search` 含羽毛球/网球用品。
- **Evidence**:
  - s2_req10 / 140921217: `prefer_brand: 尤尼克斯(rank=2), The North Face(rank=3)`; `seq_search_cat3_48h: 羽毛球用品(1), 羽毛球鞋(1)`; `seq_search_brand_48h: 威克多(2)`
  - s2_req2 / 366618992: `collect_goods: 李宁赤兔6 | 跑步鞋…; 【冠军跑鞋2代】氮科技减震跑鞋男夏季长跑运动鞋透气轻便跑步鞋; 【菱冻PRO MAX】全掌碳板跑鞋男专业马拉松减震回弹运动鞋`
- **Slogan 范例**:
  - "球场归来后的从容"（8 字）
  - "训练后给身体补一支"（9 字）
- **Anti-pattern**: "时尚之选 优雅必备"——错配运动身份。

#### E4. 塑形 / 显瘦 / 身材诉求
- **定义**: 文胸 / 塑身 / 显瘦 / 收腹 高频。
- **Evidence**:
  - stage1_req0 / 294379371: `addcart_goods: 【大胸显小 透气杯】性感网纱女士内衣文胸无钢圈收副乳显瘦胸罩(2); 小胸聚拢显大 蕾丝内衣女士文胸聚拢防下垂收副乳上托调整型胸罩`
  - s2_req5 / 404619739: `order_goods: 【液态收腹提臀 隐形显瘦】无痕塑形塑身裤女士内裤强力收小肚子`
- **Slogan 范例**:
  - "上身那一秒就显瘦"（8 字）
  - "腰那一寸 由它收住"（8 字）
- **Anti-pattern**: "舒适宽松"——刚好相反。

### F. 功能 / 健康 / 家庭场景（Functional/wellness need）

#### F1. 久坐 / 职业病 / 矫姿
- **定义**: target_product 在护肩/护腰/护膝/矫姿 cat3。
- **Evidence**:
  - s2_req1 / 16546825: target `护腰坐垫人体工学久坐不累办公室学生矫姿背坐椅垫`
  - s2_req4 / 655292256: 同一 product
  - s2_req10 / 140921217: target `艾斯凯矫姿用品驼背矫正器成人背部矫正带护腰透气矫正加压直背`
  - s2_req5 / 404619739: target `护膝夏季薄款女士空调房适用男女通用关节防寒专用夏季薄款防下滑`
- **Slogan 范例**:
  - "屏幕另一端 腰得喘口气"（10 字）
  - "弯腰这件事 今天结束"（9 字）
- **Anti-pattern**: 浪漫化"贴身呵护"——回避真实痛点。

#### F2. 家庭囤货 / 大容量心智
- **定义**: order/cart 中出现 "家庭装 / 囤货装 / 一家三口 / 大容量"，或 `order_brand` 含黄金搭档/营养保健连续单。
- **Evidence**:
  - s2_req9 / 568296523: target `按压式美白去牙垢牙渍舒缓牙齿敏感家庭囤货装`；`order_goods: 乳清蛋白粉90%增强免疫力中老年人保健品营养补充食品大豆蛋白; b族复合维生素片`
  - stage1_req0 / 294379371: `order_goods: 1L*2瓶大容量儿童牛奶洗发水沐浴露温和二合一婴幼洗护新生儿`
- **Slogan 范例**:
  - "一管够全家用半年"（8 字）
  - "屯一波 安心三个月"（8 字）
- **Anti-pattern**: 强调"小巧便携"——错配囤货心智。

#### F3. 长辈 / 自我 / 家人保健意识
- **定义**: order 中含 维生素 / 保健 / 蛋白粉 / 葡萄籽 / 中老年。
- **Evidence**:
  - s2_req9 / 568296523: `order_goods: 祛斑玫瑰花红花葡萄籽提取物祛黄褐斑保养肌肤内服男女性白; 乳清蛋白粉…中老年人保健品; b族复合维生素片…五黑营养高生物素男女士`
  - s2_req1 / 16546825: `collect_cat3: 健康秤(1)` + `addcart_brand: 艾惟诺`（婴儿护理）
- **Slogan 范例**:
  - "给家人一杯安心"（7 字）
  - "中年人的早 C 晚 A"（9 字）
- **Anti-pattern**: "潮流选择 时尚指标"——错配健康主诉。

### G. 行为漏斗姿态（Funnel posture）

#### G1. 轻浏览高转化（少 click 多 order）
- **定义**: `click_cnt_30d < 50` 但 `order_cnt_90d > 10`。
- **Evidence**:
  - s2_req3 / 222884073: `click_cnt_30d=10, order_cnt_90d=13`（点 1 单 1 的精准型）
  - stage1_req0 / 294379371: `click_cnt_30d=77, order_cnt_90d=15`
- **Slogan 范例**:
  - "你看一眼就下单的那种"（10 字）
  - "认准就这一支"（6 字）
- **Anti-pattern**: 长篇说服"快来看看 不容错过"——这类用户不需要劝。

#### G2. 信息饕餮型（千 click 数十 order）
- **定义**: `click_cnt_30d > 800`。
- **Evidence**:
  - s2_req5 / 404619739: `click_cnt_30d=1338, order_cnt_30d=3`
  - s2_req10 / 140921217: `click_cnt_30d=2050, order_cnt_30d=22`
  - s2_req1 / 16546825: `click_cnt_30d=792, order_cnt_30d=4`
- **Slogan 范例**:
  - "千件比过 还是它最对"（9 字）
  - "看遍全网 唯独把它放进车"（11 字）
- **Anti-pattern**: 单薄的"必入款 别错过"——比不过她自己已比过的千个 click。

---

## 3. Angle 维度性分析（dimensionality）

将 25 个 angles 归为 7 个 latent dimensions，标注高/中/低 variance（在 11 请求 / 9 独立用户样本上）：

| Dimension | Angles | 样本 variance | 是否值得作为 slogan-策略主轴 |
|---|---|---|---|
| **D1 身份与生命阶段** (Identity & life-stage) | A1, A2, A3, A4, A5 | **高**：age 跨度 31–49、有娃/无娃、男女代理、新老用户都有覆盖 | ✅ 主轴 |
| **D2 经济姿态** (Economic posture) | B1, B2, B3, B4, B5, B6 | **高**：ASP 从 ¥30 到 ¥234（约 8×）；coupon 0–11；价格跨级（4.88× 跃迁 + 0.20× 下沉）都有 | ✅ 主轴 |
| **D3 品牌关系** (Brand relationship) | C1, C2, C3 | **中-高**：从死忠（红袖/巴拉巴拉）到 91-brand 收藏家 + 1 例双 aligned 复购 | ✅ 主轴 |
| **D4 时间/地域上下文** (Temporal & regional) | D1, D2, D3, D4, D5 | **中**：hour 跨 8/9/13/14/18/21/22/23（饱满），region_level 6 省份。**day_of_week 全部=3（周三）→零方差，无法当主轴** | ⚠️ 部分用，避用 day_of_week |
| **D5 美学身份** (Aesthetic identity) | E1, E2, E3, E4 | **中**：新中式 2 例、运动 2 例、塑形 2 例、多巴胺 2 例——每类小但都有覆盖 | ✅ 主轴 |
| **D6 功能/健康/家庭场景** (Functional / wellness) | F1, F2, F3 | **中**：4 例职业病矫姿、2 例囤货、2 例保健——target 类目自带强信号 | ✅ 主轴 |
| **D7 行为漏斗姿态** (Funnel posture) | G1, G2 | **中**：少 click 多 order 2 例、信息饕餮 3 例——可帮助调修辞强度 | ☑ 二级修饰，不单独立轴 |

**高 variance（材料丰盛、最差异化的维度）**: D1 身份与生命阶段、D2 经济姿态。
**低 variance（在本样本中无法差异化）**: `context.day_of_week` 全=3 → 完全无信号；`gender_match_item_gender_tag` 几乎全 0 → 商品与用户性别匹配不显著；`is_cold_start_combo` 仅 1 例 true（s2_req6）→ 难支撑独立角度。

---

## 4. 8–16 字表达力分析（"the 8–16 char trap"）

### 高表达力角度（在 8–16 字中能保留辨识度）

| Angle | 范例 (字数) | 关键技巧 |
|---|---|---|
| A1 长尾老客户 | "金卡第八年的小确幸"（10） | 把 `register_days` 翻译成"第 N 年"，量词具体 |
| B1 价格地板派 | "大牌也敢平价拿下"（8） | 用"敢"字制造价值反差 |
| B5 品牌跨级 | "第一次试国际大牌的味道"（10） | "第一次"承担首购心智 |
| C1 单品牌死忠 | "红袖之外 还有它撑场"（9） | 直接呼名 + 让位 |
| E1 新中式 | "再添一抹东方调"（7） | "添"暗示已有 = 老客户感 |
| F1 久坐矫姿 | "屏幕另一端 腰得喘口气"（10） | 场景拟人化 |
| F2 家庭囤货 | "一管够全家用半年"（8） | 量化承诺 |
| D1 深夜 | "哄睡后 给自己的小礼物"（10） | 时段 + 行为 + 自我 |
| A5 中年女性 | "四十岁那点小自私"（8） | 直面年龄 + "私"字代偿 |
| G2 信息饕餮 | "千件比过 还是它最对"（9） | "千件"映射 click_cnt |

### 低表达力角度（8–16 字内难以传达，**需结构性妥协**）

| Angle | 难点 | 妥协方案 |
|---|---|---|
| B3 收藏夹堆积 | 需说明"你已收 N 件但没下单" + "该这一件了"——双 clause 难压缩 | 只保留后半："收藏夹的句号"（6）——但前提缺失 |
| B5 + C1 复合 | "你最爱红袖 但今天该尝试国际大牌"——两条心智叠加难融 | 牺牲一条；优先 brand-tier leap |
| D4 + E3 复合 | "陕西春风 × 英伦风衣"——区域 + 美学 + 品类 三层 | 选最强一层（美学） |
| C2 多品牌博物馆 | 想说"已 91 品牌 + 1"——数字精准但生硬 | 退化为"图鉴又添一页"，丢精度 |
| F3 自他兼顾 | "给爸妈/老公/孩子 + 给自己" 多对象一句难分 | 选最强对象（家人 OR 自己） |

**结论**: 8–16 字预算对**单维度尖刀**最友好，对**多维度叠合**有硬上限。Slogan 工程应在单 trial 内**强制选取 1 个主轴 + 至多 1 个修饰子轴**，而非同时叠 3 个维度。

---

## 5. 产品名冗余批评（avoiding product-name redundancy）

11 个 target product 的 canonical_product_name 都已包含 cat3 名词（香水 / 防晒乳 / 护腰坐垫 / 护膝 / 牙膏 / 矫姿器 / 香水套组）。Slogan 若再次写出品名/品类名，意义重复，且占用 8–16 字宝贵预算。

**论点：除少数 angles 必须借品牌名/类目名做反差（B5、C1、C3），其余 angles 均可**让 slogan 完全不出现品类名、改用桥接意象（手段=动作、感受、场景、对象、时间）**。

### 桥接示例（angle → 不带品名的 slogan）

| Angle | Target | 桥接式 slogan（无品名/品类名） | 桥接手法 |
|---|---|---|---|
| A2 多娃妈妈 | 兰蔻香水 ¥249 | "哄完一柜 给自己留一支"（10） | 动作"哄完" + 量词"一柜" + 对象"自己" |
| F1 久坐矫姿 | 艾斯凯矫姿器 ¥48 | "弯腰这件事 今天结束"（9） | 抽象动作"弯腰" + 时间承诺"今天" |
| F2 囤货 | 牙膏家庭装 ¥56 | "一管够全家用半年"（8） | 量词"一管" + 受益对象"全家" + 时长"半年" |
| D4 区域气候 | 兰蔻香水（云南用户） | "云南春暖 也得有一缕香"（10） | 地域 + 季节 + 拟态"一缕香"（绕开"香水"） |
| E3 运动 tech | 护腰坐垫 ¥25（s2_req4 运动男新人） | "球场之外 腰也得有人疼"（10） | 场景对比 + 身体部位"腰"（指代产品功用） |
| B5 品牌跃迁 | 兰蔻香水 ¥249 | "第一次给衣柜添个国际名"（11） | 用"国际名"取代"兰蔻 / 香水" |
| A4 新用户 | 护腰坐垫 ¥25 | "新人这一单 就当见面礼"（10） | 用"这一单"取代"坐垫" |
| C1 单品牌死忠 | 浪漫香水 ¥49（无具体强品牌） | "你那一柜熟悉的味 加一支新调"（12） | "新调"取代"香水" |

**少数必须出现品牌名 / 类目名的反例**：
- C1（红袖之外 还有它撑场）—— "红袖" 是用户偏好品牌，借势必需。
- B5（你的衣柜该添一支外国香）—— "外国香" 是品类抽象，已规避具体品牌名。
- F1 多数情况下"腰" / "颈" / "驼背" 等身体部位词比类目名更高密度。

**经验法则建议**: 默认假设"slogan 不写品类名"为铁律；只有当 angle 借势品牌名时才允许品牌出现，且品牌出现也最好是"用户先验品牌（red anchor）"而非"target 品牌（vendor anchor）"。

---

## 6. 自检（self-check）

- **样本规模坦白**: 11 reqs / 9 独立用户。每个 angle 至少 2 条 evidence 来自不同 user_id；标注为"低 prevalence"的 angles（A4 / B2 / B4 / C3 / D5）仅 1 用户支撑，请按低先验对待，不强行叠加。
- **未涉及读取**: 没有读取任何 SKILL.md、copy_generation 输出、rubric judgments、code、parallel agent 的 findings。本文件不引用任何外部判断，只引用 11 份 payload 中的 verbatim 字段。
- **零方差字段披露**: `context.day_of_week` 全为 3（周三）—— **不能**作为 slogan 维度；`gender_match_item_gender_tag` 几乎全 0；`is_exclusive` 全 0。

---

## 附：可机检 angle → field-rule 索引（供下游 skill 引用时直接 grep）

| ID | 触发字段（field-level rule） |
|---|---|
| A1 | `profile.register_days > 2000` AND `profile.vip_level ∈ {金卡, 白金卡}` |
| A2 | `behavior.prefer_cat3_topK` 前 5 项中 ≥3 项以"儿童/婴幼"开头 AND `profile.gender=女` |
| A3 | `profile.gender=男` AND（`prefer_cat3` 前 5 中 ≥2 项女装 OR `order_goods` 含"女童/女式/女士"） |
| A4 | `profile.register_days < 200` |
| A5 | `profile.age ∈ [40, 50]` AND `profile.gender=女` |
| B1 | `profile.purchase_price_avg_30d < 50` |
| B2 | `profile.purchase_price_avg_30d > 150` AND `profile.fav_price_avg_30d > 150` |
| B3 | `profile.fav_brand_cnt_30d >= 2 * order_cnt_30d` 或 `fav_price_avg_30d >= 2 * purchase_price_avg_30d` |
| B4 | `profile.coupon_use_cnt_30d >= 3` |
| B5 | `derived.price_vs_user_baseline_bucket ∈ {远高于, 远超出}` AND `derived.brand_alignment=mismatch` |
| B6 | `derived.price_vs_user_baseline_bucket=远低于` AND `profile.purchase_price_avg_30d > 100` |
| C1 | `behavior.click_brand_id_list_topN` 第一名 click 数 ≥ 第二名 5× |
| C2 | `profile.fav_brand_cnt_30d >= 40` |
| C3 | `derived.cat3_alignment=aligned` AND `derived.brand_alignment=aligned` |
| D1 | `context.hour ∈ [22, 1]` AND `profile.click_cnt_30d >= 100` |
| D2 | `context.hour ∈ [7, 9]` AND `context.device_type=iPhone` |
| D3 | `context.hour ∈ [13, 15]` AND `profile.gender=女` AND `profile.vip_level ∈ {金卡, 白金卡}` |
| D4 | `profile.region_level` 与 target 季节/气候关联 |
| D5 | `profile.order_cnt_30d / max(1, order_cnt_90d) >= 0.8` |
| E1 | `behavior.order_goods` / `click_goods` 含"新中式/汉服/旗袍/盘扣/国风" |
| E2 | `behavior.order_goods` / `click_goods` 含"多巴胺/撞色/印花标语/趣味" |
| E3 | `behavior.prefer_brand` 含运动专业品牌 OR `seq_search` 含球类品类 |
| E4 | `behavior.addcart_goods` / `order_goods` 含"显瘦/塑形/收腹/聚拢" |
| F1 | `target.category ∈ {护肩, 护腰, 护膝, 矫姿}` |
| F2 | target canonical 含"家庭/囤货/装/大容量" OR order 中保健连续多单 |
| F3 | `behavior.order_goods` 含维生素 / 保健 / 蛋白粉 / 葡萄籽 / 中老年 |
| G1 | `profile.click_cnt_30d < 100` AND `profile.order_cnt_90d >= 10` |
| G2 | `profile.click_cnt_30d > 800` |

import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { p as pluginBase, f as formatHourlyBonus, a as formatTb, u as unwrapResponse } from './provider-nhLRPrSl.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper-pcqpp-6-.js';

const {createElementVNode:_createElementVNode,resolveComponent:_resolveComponent,createVNode:_createVNode,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,withCtx:_withCtx,openBlock:_openBlock,createBlock:_createBlock,createCommentVNode:_createCommentVNode,createElementBlock:_createElementBlock,renderList:_renderList,Fragment:_Fragment,normalizeClass:_normalizeClass,unref:_unref} = await importShared('vue');


const _hoisted_1 = { class: "sitebonus-app-page" };
const _hoisted_2 = {
  key: 0,
  class: "d-flex align-center mb-4"
};
const _hoisted_3 = { class: "summary-grid mb-2" };
const _hoisted_4 = { class: "text-h5 text-primary mt-1" };
const _hoisted_5 = { class: "text-h5 text-primary mt-1" };
const _hoisted_6 = { class: "mt-auto text-caption text-medium-emphasis summary-sub" };
const _hoisted_7 = { class: "text-h5 text-primary mt-1" };
const _hoisted_8 = { class: "text-h5 text-primary mt-1" };
const _hoisted_9 = { class: "mt-auto text-caption text-medium-emphasis summary-sub" };
const _hoisted_10 = ["onClick"];
const _hoisted_11 = { class: "th-inner" };
const _hoisted_12 = { key: 0 };
const _hoisted_13 = { class: "ps-2" };
const _hoisted_14 = ["href"];
const _hoisted_15 = { class: "text-end" };
const _hoisted_16 = { class: "text-end" };
const _hoisted_17 = { class: "text-end" };
const _hoisted_18 = { class: "text-end" };
const _hoisted_19 = { class: "text-end" };
const _hoisted_20 = { class: "text-end" };
const _hoisted_21 = { class: "text-end" };
const _hoisted_22 = { class: "text-caption" };
const _hoisted_23 = { key: 1 };
const _hoisted_24 = {
  colspan: "11",
  class: "text-center text-medium-emphasis py-4"
};

const {computed,onMounted,ref} = await importShared('vue');


const _sfc_main = {
  __name: 'AppPage',
  props: {
  api: {
    type: Object,
    default: () => ({}),
  },
  pluginId: {
    type: String,
    default: 'SiteBonusMonitor',
  },
  hideTitle: {
    type: Boolean,
    default: false,
  },
},
  setup(__props, { expose: __expose }) {

const props = __props;

const loading = ref(false);
const error = ref('');
const metrics = ref([]);
const lastUpdated = ref('');

// 排序状态：null 表示未排序（保持原始顺序）
const sortKey = ref(null);
const sortDir = ref('asc'); // 'asc' | 'desc'

// 列定义：key、label、对齐、排序取值函数
const columns = [
  { key: 'site_name', label: '站点', align: 'start', getter: r => r.site_name || '' },
  { key: 'username', label: '用户', align: 'start', getter: r => r.username || '' },
  { key: 'user_level', label: '等级', align: 'start', getter: r => r.user_level || '' },
  { key: 'bonus', label: '魔力值', align: 'end', getter: r => r.bonus || 0 },
  { key: 'seeding', label: '做种', align: 'end', getter: r => r.seeding || 0 },
  { key: 'hourly_bonus', label: '时魔', align: 'end', getter: r => (r.hourly_bonus ?? -Infinity) },
  { key: 'upload_gb', label: '上传', align: 'end', getter: r => r.upload_gb || 0 },
  { key: 'download_gb', label: '下载', align: 'end', getter: r => r.download_gb || 0 },
  { key: 'ratio', label: '分享率', align: 'end', getter: r => r.ratio || 0 },
  { key: 'window_hours', label: '窗口(h)', align: 'end', getter: r => r.window_hours || 0 },
  { key: 'updated_at', label: '更新时间', align: 'start', getter: r => r.updated_at || '' },
];

function toggleSort(key) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc';
  } else {
    sortKey.value = key;
    sortDir.value = 'asc';
  }
}

const base = computed(() => pluginBase(props.pluginId));

async function loadMetrics(showLoading = true) {
  if (showLoading) loading.value = true;
  error.value = '';
  try {
    const response = await props.api.get(`${base.value}/metrics`);
    metrics.value = unwrapResponse(response) || [];
    lastUpdated.value = new Date().toLocaleString('zh-CN', { hour12: false });
  } catch (err) {
    error.value = err?.message || '加载站点数据失败';
  } finally {
    if (showLoading) loading.value = false;
  }
}

onMounted(() => {
  loadMetrics();
});

const validMetrics = computed(() => metrics.value.filter(m => m.hourly_bonus !== null && m.hourly_bonus !== undefined));
computed(() => [...validMetrics.value].sort((a, b) => (b.hourly_bonus || 0) - (a.hourly_bonus || 0)));
const summary = computed(() => {
  const list = metrics.value;
  const valid = validMetrics.value;
  const totalBonus = list.reduce((sum, m) => sum + (m.bonus || 0), 0);
  const totalSeeding = list.reduce((sum, m) => sum + (m.seeding || 0), 0);
  const totalHourly = valid.reduce((sum, m) => sum + (m.hourly_bonus || 0), 0);
  return {
    sites: list.length,
    bonus: totalBonus,
    seeding: totalSeeding,
    hourly: totalHourly,
    validCount: valid.length,
  }
});

const sortedMetrics = computed(() => {
  if (!sortKey.value) return metrics.value
  const col = columns.find(c => c.key === sortKey.value);
  if (!col) return metrics.value
  const getter = col.getter;
  const list = [...metrics.value];
  list.sort((a, b) => {
    const va = getter(a);
    const vb = getter(b);
    if (typeof va === 'string' || typeof vb === 'string') {
      const cmp = String(va).localeCompare(String(vb), 'zh-CN');
      return sortDir.value === 'asc' ? cmp : -cmp
    }
    return sortDir.value === 'asc' ? va - vb : vb - va
  });
  return list
});

function sortIcon(key) {
  if (sortKey.value !== key) return 'mdi-unfold-more-horizontal'
  return sortDir.value === 'asc' ? 'mdi-arrow-up' : 'mdi-arrow-down'
}

__expose({ loadMetrics, loading });

return (_ctx, _cache) => {
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VCard = _resolveComponent("VCard");
  const _component_VIcon = _resolveComponent("VIcon");
  const _component_VTable = _resolveComponent("VTable");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    (!__props.hideTitle)
      ? (_openBlock(), _createElementBlock("div", _hoisted_2, [
          _cache[2] || (_cache[2] = _createElementVNode("div", { class: "text-h6" }, "📊 站点魔力值监控", -1)),
          _createVNode(_component_VSpacer),
          (lastUpdated.value)
            ? (_openBlock(), _createBlock(_component_VChip, {
                key: 0,
                size: "small",
                variant: "tonal",
                color: "primary"
              }, {
                default: _withCtx(() => [
                  _createTextVNode(" 更新于 " + _toDisplayString(lastUpdated.value), 1)
                ]),
                _: 1
              }))
            : _createCommentVNode("", true),
          _createVNode(_component_VBtn, {
            icon: "mdi-refresh",
            variant: "text",
            loading: loading.value,
            class: "ms-2",
            onClick: _cache[0] || (_cache[0] = $event => (loadMetrics()))
          }, null, 8, ["loading"])
        ]))
      : _createCommentVNode("", true),
    (error.value)
      ? (_openBlock(), _createBlock(_component_VAlert, {
          key: 1,
          type: "error",
          variant: "tonal",
          closable: "",
          class: "mb-3",
          "onClick:close": _cache[1] || (_cache[1] = $event => (error.value = ''))
        }, {
          default: _withCtx(() => [
            _createTextVNode(_toDisplayString(error.value), 1)
          ]),
          _: 1
        }))
      : _createCommentVNode("", true),
    _createElementVNode("div", _hoisted_3, [
      _createVNode(_component_VCard, {
        variant: "tonal",
        class: "summary-card"
      }, {
        default: _withCtx(() => [
          _createVNode(_component_VCardText, { class: "d-flex flex-column summary-text" }, {
            default: _withCtx(() => [
              _cache[3] || (_cache[3] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "启用站点", -1)),
              _createElementVNode("div", _hoisted_4, _toDisplayString(summary.value.sites), 1),
              _cache[4] || (_cache[4] = _createElementVNode("div", { class: "mt-auto text-caption text-medium-emphasis summary-sub" }, " ", -1))
            ]),
            _: 1
          })
        ]),
        _: 1
      }),
      _createVNode(_component_VCard, {
        variant: "tonal",
        class: "summary-card"
      }, {
        default: _withCtx(() => [
          _createVNode(_component_VCardText, { class: "d-flex flex-column summary-text" }, {
            default: _withCtx(() => [
              _cache[5] || (_cache[5] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "总魔力值", -1)),
              _createElementVNode("div", _hoisted_5, _toDisplayString(summary.value.bonus.toFixed(2)), 1),
              _createElementVNode("div", _hoisted_6, "来自 " + _toDisplayString(summary.value.sites) + " 个站点", 1)
            ]),
            _: 1
          })
        ]),
        _: 1
      }),
      _createVNode(_component_VCard, {
        variant: "tonal",
        class: "summary-card"
      }, {
        default: _withCtx(() => [
          _createVNode(_component_VCardText, { class: "d-flex flex-column summary-text" }, {
            default: _withCtx(() => [
              _cache[6] || (_cache[6] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "总做种数", -1)),
              _createElementVNode("div", _hoisted_7, _toDisplayString(summary.value.seeding), 1),
              _cache[7] || (_cache[7] = _createElementVNode("div", { class: "mt-auto text-caption text-medium-emphasis summary-sub" }, "活跃种子总数", -1))
            ]),
            _: 1
          })
        ]),
        _: 1
      }),
      _createVNode(_component_VCard, {
        variant: "tonal",
        class: "summary-card"
      }, {
        default: _withCtx(() => [
          _createVNode(_component_VCardText, { class: "d-flex flex-column summary-text" }, {
            default: _withCtx(() => [
              _cache[8] || (_cache[8] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "总时魔 (24h)", -1)),
              _createElementVNode("div", _hoisted_8, _toDisplayString(summary.value.hourly >= 0 ? '+' : '') + _toDisplayString(summary.value.hourly.toFixed(4)), 1),
              _createElementVNode("div", _hoisted_9, _toDisplayString(summary.value.validCount) + " / " + _toDisplayString(summary.value.sites) + " 个站点有效", 1)
            ]),
            _: 1
          })
        ]),
        _: 1
      })
    ]),
    _createVNode(_component_VAlert, {
      type: "info",
      variant: "tonal",
      density: "compact",
      class: "my-3"
    }, {
      default: _withCtx(() => [...(_cache[9] || (_cache[9] = [
        _createTextVNode(" 时魔 = 最近 24 小时内最早与最新魔力值快照的差值 / 小时数；窗口长度见「窗口(h)」列。 ", -1)
      ]))]),
      _: 1
    }),
    _createVNode(_component_VTable, {
      density: "compact",
      hover: ""
    }, {
      default: _withCtx(() => [
        _createElementVNode("thead", null, [
          _createElementVNode("tr", null, [
            (_openBlock(), _createElementBlock(_Fragment, null, _renderList(columns, (col) => {
              return _createElementVNode("th", {
                key: col.key,
                class: _normalizeClass(`text-${col.align} sortable-th`),
                onClick: $event => (toggleSort(col.key))
              }, [
                _createElementVNode("span", _hoisted_11, [
                  _createElementVNode("span", null, _toDisplayString(col.label), 1),
                  _createVNode(_component_VIcon, {
                    icon: sortIcon(col.key),
                    size: "small",
                    class: "ms-1 sort-icon"
                  }, null, 8, ["icon"])
                ])
              ], 10, _hoisted_10)
            }), 64))
          ])
        ]),
        (sortedMetrics.value.length)
          ? (_openBlock(), _createElementBlock("tbody", _hoisted_12, [
              (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(sortedMetrics.value, (row) => {
                return (_openBlock(), _createElementBlock("tr", {
                  key: row.site_id
                }, [
                  _createElementVNode("td", _hoisted_13, [
                    _createElementVNode("a", {
                      href: row.url,
                      target: "_blank",
                      rel: "noopener",
                      class: "text-primary"
                    }, _toDisplayString(row.site_name), 9, _hoisted_14)
                  ]),
                  _createElementVNode("td", null, _toDisplayString(row.username || '-'), 1),
                  _createElementVNode("td", null, _toDisplayString(row.user_level || '-'), 1),
                  _createElementVNode("td", _hoisted_15, _toDisplayString(row.bonus.toFixed(2)), 1),
                  _createElementVNode("td", _hoisted_16, _toDisplayString(row.seeding), 1),
                  _createElementVNode("td", _hoisted_17, [
                    _createVNode(_component_VChip, {
                      size: "x-small",
                      color: (row.hourly_bonus ?? 0) >= 0 ? 'primary' : 'grey',
                      variant: "tonal"
                    }, {
                      default: _withCtx(() => [
                        _createTextVNode(_toDisplayString(_unref(formatHourlyBonus)(row.hourly_bonus)), 1)
                      ]),
                      _: 2
                    }, 1032, ["color"])
                  ]),
                  _createElementVNode("td", _hoisted_18, _toDisplayString(_unref(formatTb)(row.upload_gb)), 1),
                  _createElementVNode("td", _hoisted_19, _toDisplayString(_unref(formatTb)(row.download_gb)), 1),
                  _createElementVNode("td", _hoisted_20, _toDisplayString(row.ratio.toFixed(3)), 1),
                  _createElementVNode("td", _hoisted_21, _toDisplayString(row.window_hours.toFixed(1)), 1),
                  _createElementVNode("td", _hoisted_22, _toDisplayString(row.updated_at || '-'), 1)
                ]))
              }), 128))
            ]))
          : (_openBlock(), _createElementBlock("tbody", _hoisted_23, [
              _createElementVNode("tr", null, [
                _createElementVNode("td", _hoisted_24, _toDisplayString(loading.value ? '加载中…' : '暂无站点数据'), 1)
              ])
            ]))
      ]),
      _: 1
    })
  ]))
}
}

};
const AppPage = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-f6223b00"]]);

export { AppPage as default };

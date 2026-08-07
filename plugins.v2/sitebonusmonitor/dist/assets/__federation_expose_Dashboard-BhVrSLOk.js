import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { f as formatHourlyBonus, u as unwrapResponse } from './provider-nhLRPrSl.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper-pcqpp-6-.js';

const {createElementVNode:_createElementVNode,renderList:_renderList,Fragment:_Fragment,openBlock:_openBlock,createElementBlock:_createElementBlock,toDisplayString:_toDisplayString,createTextVNode:_createTextVNode,resolveComponent:_resolveComponent,withCtx:_withCtx,createVNode:_createVNode,unref:_unref,createBlock:_createBlock,createCommentVNode:_createCommentVNode} = await importShared('vue');


const _hoisted_1 = { class: "sitebonus-dashboard" };
const _hoisted_2 = {
  key: 0,
  class: "d-flex flex-column",
  style: {"gap":"16px"}
};
const _hoisted_3 = {
  key: 1,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_4 = {
  class: "d-flex flex-wrap align-stretch",
  style: {"gap":"12px"}
};
const _hoisted_5 = { class: "metric-cell" };
const _hoisted_6 = { class: "text-h6 text-primary mt-1" };
const _hoisted_7 = { class: "metric-cell" };
const _hoisted_8 = { class: "text-h6 text-primary mt-1" };
const _hoisted_9 = { class: "metric-cell" };
const _hoisted_10 = { class: "text-h6 text-primary mt-1" };
const _hoisted_11 = { class: "metric-cell" };
const _hoisted_12 = { class: "text-h6 text-primary mt-1" };
const _hoisted_13 = {
  key: 1,
  class: "text-caption text-medium-emphasis"
};
const _hoisted_14 = {
  key: 2,
  class: "text-caption text-medium-emphasis"
};

const {computed,onMounted,onUnmounted,ref} = await importShared('vue');


const _sfc_main = {
  __name: 'Dashboard',
  props: {
  api: {
    type: Object,
    default: () => ({}),
  },
  allowRefresh: {
    type: Boolean,
    default: true,
  },
},
  setup(__props) {

const props = __props;

const loading = ref(false);
const metrics = ref([]);
let timer = null;

const validMetrics = computed(() =>
  metrics.value.filter(m => m.hourly_bonus !== null && m.hourly_bonus !== undefined)
);
const topMetrics = computed(() =>
  [...validMetrics.value].sort((a, b) => (b.hourly_bonus || 0) - (a.hourly_bonus || 0)).slice(0, 8)
);
const summary = computed(() => {
  const list = metrics.value;
  const valid = validMetrics.value;
  return {
    sites: list.length,
    bonus: list.reduce((sum, m) => sum + (m.bonus || 0), 0),
    seeding: list.reduce((sum, m) => sum + (m.seeding || 0), 0),
    hourly: valid.reduce((sum, m) => sum + (m.hourly_bonus || 0), 0),
    validCount: valid.length,
  }
});

async function loadStatus() {
  if (!props.allowRefresh) return
  loading.value = true;
  try {
    const response = await props.api.get('plugin/SiteBonusMonitor/metrics');
    metrics.value = unwrapResponse(response) || [];
  } catch (err) {
    // 静默失败
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  loadStatus();
  timer = window.setInterval(loadStatus, 60000);
});

onUnmounted(() => {
  if (timer) {
    window.clearInterval(timer);
  }
});

return (_ctx, _cache) => {
  const _component_VListItemTitle = _resolveComponent("VListItemTitle");
  const _component_VListItemSubtitle = _resolveComponent("VListItemSubtitle");
  const _component_VChip = _resolveComponent("VChip");
  const _component_VListItem = _resolveComponent("VListItem");
  const _component_VList = _resolveComponent("VList");
  const _component_VDivider = _resolveComponent("VDivider");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    (summary.value.sites > 0)
      ? (_openBlock(), _createElementBlock("div", _hoisted_2, [
          _createElementVNode("div", null, [
            _cache[0] || (_cache[0] = _createElementVNode("div", { class: "text-caption text-medium-emphasis mb-2" }, "时魔 Top 站点", -1)),
            (topMetrics.value.length)
              ? (_openBlock(), _createBlock(_component_VList, {
                  key: 0,
                  density: "compact"
                }, {
                  default: _withCtx(() => [
                    (_openBlock(true), _createElementBlock(_Fragment, null, _renderList(topMetrics.value, (m) => {
                      return (_openBlock(), _createBlock(_component_VListItem, {
                        key: m.site_id
                      }, {
                        append: _withCtx(() => [
                          _createVNode(_component_VChip, {
                            size: "small",
                            color: (m.hourly_bonus || 0) >= 0 ? 'primary' : 'grey',
                            variant: "tonal"
                          }, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(_unref(formatHourlyBonus)(m.hourly_bonus)) + " /h ", 1)
                            ]),
                            _: 2
                          }, 1032, ["color"])
                        ]),
                        default: _withCtx(() => [
                          _createVNode(_component_VListItemTitle, null, {
                            default: _withCtx(() => [
                              _createTextVNode(_toDisplayString(m.site_name), 1)
                            ]),
                            _: 2
                          }, 1024),
                          _createVNode(_component_VListItemSubtitle, null, {
                            default: _withCtx(() => [
                              _createTextVNode("魔力 " + _toDisplayString(m.bonus.toFixed(2)) + " · 做种 " + _toDisplayString(m.seeding), 1)
                            ]),
                            _: 2
                          }, 1024)
                        ]),
                        _: 2
                      }, 1024))
                    }), 128))
                  ]),
                  _: 1
                }))
              : (_openBlock(), _createElementBlock("div", _hoisted_3, "暂无 24h 内有效数据"))
          ]),
          _createVNode(_component_VDivider),
          _createElementVNode("div", _hoisted_4, [
            _createElementVNode("div", _hoisted_5, [
              _cache[1] || (_cache[1] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "总魔力值", -1)),
              _createElementVNode("div", _hoisted_6, _toDisplayString(summary.value.bonus.toFixed(2)), 1)
            ]),
            _createElementVNode("div", _hoisted_7, [
              _cache[2] || (_cache[2] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "总做种", -1)),
              _createElementVNode("div", _hoisted_8, _toDisplayString(summary.value.seeding), 1)
            ]),
            _createElementVNode("div", _hoisted_9, [
              _cache[3] || (_cache[3] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "总时魔", -1)),
              _createElementVNode("div", _hoisted_10, _toDisplayString(summary.value.hourly >= 0 ? '+' : '') + _toDisplayString(summary.value.hourly.toFixed(4)), 1)
            ]),
            _createElementVNode("div", _hoisted_11, [
              _cache[4] || (_cache[4] = _createElementVNode("div", { class: "text-caption text-medium-emphasis" }, "有效站点", -1)),
              _createElementVNode("div", _hoisted_12, _toDisplayString(summary.value.validCount) + " / " + _toDisplayString(summary.value.sites), 1)
            ])
          ])
        ]))
      : (!loading.value)
        ? (_openBlock(), _createElementBlock("div", _hoisted_13, " 暂无站点数据，等待 MoviePilot 采集 "))
        : (_openBlock(), _createElementBlock("div", _hoisted_14, "加载中..."))
  ]))
}
}

};
const Dashboard = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-98b24acc"]]);

export { Dashboard as default };

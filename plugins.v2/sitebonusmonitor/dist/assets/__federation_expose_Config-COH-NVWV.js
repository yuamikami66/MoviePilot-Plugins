import { importShared } from './__federation_fn_import-JrT3xvdd.js';
import { _ as _export_sfc } from './_plugin-vue_export-helper-pcqpp-6-.js';

const {createTextVNode:_createTextVNode,resolveComponent:_resolveComponent,withCtx:_withCtx,createVNode:_createVNode,createElementVNode:_createElementVNode,openBlock:_openBlock,createElementBlock:_createElementBlock} = await importShared('vue');


const _hoisted_1 = { class: "sitebonus-config" };

const {onMounted,ref} = await importShared('vue');



const _sfc_main = {
  __name: 'Config',
  props: {
  initialConfig: {
    type: Object,
    default: () => ({}),
  },
},
  emits: ['save', 'close'],
  setup(__props, { emit: __emit }) {

const props = __props;

const emit = __emit;

const localConfig = ref({
  enabled: false,
  cron: '0 8 * * *',
  notify_only_success: true,
});

function cloneConfig(config) {
  return JSON.parse(JSON.stringify(config || {}))
}

function saveConfig() {
  emit('save', cloneConfig(localConfig.value));
}

onMounted(() => {
  localConfig.value = {
    enabled: Boolean(props.initialConfig.enabled),
    cron: String(props.initialConfig.cron || '0 8 * * *'),
    notify_only_success: Boolean(props.initialConfig.notify_only_success),
  };
});

return (_ctx, _cache) => {
  const _component_VCardTitle = _resolveComponent("VCardTitle");
  const _component_VSwitch = _resolveComponent("VSwitch");
  const _component_VCol = _resolveComponent("VCol");
  const _component_VTextField = _resolveComponent("VTextField");
  const _component_VRow = _resolveComponent("VRow");
  const _component_VAlert = _resolveComponent("VAlert");
  const _component_VCardText = _resolveComponent("VCardText");
  const _component_VDivider = _resolveComponent("VDivider");
  const _component_VSpacer = _resolveComponent("VSpacer");
  const _component_VBtn = _resolveComponent("VBtn");
  const _component_VCardActions = _resolveComponent("VCardActions");
  const _component_VCard = _resolveComponent("VCard");

  return (_openBlock(), _createElementBlock("div", _hoisted_1, [
    _createVNode(_component_VCard, { variant: "tonal" }, {
      default: _withCtx(() => [
        _createVNode(_component_VCardTitle, { class: "text-h6" }, {
          default: _withCtx(() => [...(_cache[4] || (_cache[4] = [
            _createTextVNode("📊 站点魔力值监控", -1)
          ]))]),
          _: 1
        }),
        _createVNode(_component_VCardText, null, {
          default: _withCtx(() => [
            _createVNode(_component_VRow, null, {
              default: _withCtx(() => [
                _createVNode(_component_VCol, { cols: "12" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VSwitch, {
                      modelValue: localConfig.value.enabled,
                      "onUpdate:modelValue": _cache[0] || (_cache[0] = $event => ((localConfig.value.enabled) = $event)),
                      label: "启用插件",
                      color: "primary",
                      density: "comfortable",
                      "hide-details": ""
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_VCol, { cols: "12" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VTextField, {
                      modelValue: localConfig.value.cron,
                      "onUpdate:modelValue": _cache[1] || (_cache[1] = $event => ((localConfig.value.cron) = $event)),
                      label: "定时推送 Cron",
                      placeholder: "0 8 * * *",
                      "prepend-inner-icon": "mdi-clock-outline",
                      hint: "5 段标准 cron；留空则不推送通知",
                      "persistent-hint": ""
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                }),
                _createVNode(_component_VCol, { cols: "12" }, {
                  default: _withCtx(() => [
                    _createVNode(_component_VSwitch, {
                      modelValue: localConfig.value.notify_only_success,
                      "onUpdate:modelValue": _cache[2] || (_cache[2] = $event => ((localConfig.value.notify_only_success) = $event)),
                      label: "仅在数据有变化时推送",
                      color: "primary",
                      density: "comfortable",
                      "hide-details": ""
                    }, null, 8, ["modelValue"])
                  ]),
                  _: 1
                })
              ]),
              _: 1
            }),
            _createVNode(_component_VAlert, {
              type: "info",
              variant: "tonal",
              density: "compact",
              class: "mt-3"
            }, {
              default: _withCtx(() => [...(_cache[5] || (_cache[5] = [
                _createTextVNode(" 数据来源：MoviePilot 站点用户数据表（SiteUserData）。", -1),
                _createElementVNode("br", null, null, -1),
                _createTextVNode(" 时魔 = 最近 24 小时内最早与最新魔力值快照差值 / 小时数。 ", -1)
              ]))]),
              _: 1
            })
          ]),
          _: 1
        }),
        _createVNode(_component_VDivider),
        _createVNode(_component_VCardActions, null, {
          default: _withCtx(() => [
            _createVNode(_component_VSpacer),
            _createVNode(_component_VBtn, {
              variant: "text",
              onClick: _cache[3] || (_cache[3] = $event => (emit('close')))
            }, {
              default: _withCtx(() => [...(_cache[6] || (_cache[6] = [
                _createTextVNode("取消", -1)
              ]))]),
              _: 1
            }),
            _createVNode(_component_VBtn, {
              variant: "tonal",
              color: "primary",
              onClick: saveConfig
            }, {
              default: _withCtx(() => [...(_cache[7] || (_cache[7] = [
                _createTextVNode("保存", -1)
              ]))]),
              _: 1
            })
          ]),
          _: 1
        })
      ]),
      _: 1
    })
  ]))
}
}

};
const Config = /*#__PURE__*/_export_sfc(_sfc_main, [['__scopeId',"data-v-4b46c022"]]);

export { Config as default };

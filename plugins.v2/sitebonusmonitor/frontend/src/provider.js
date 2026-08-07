/**
 * 站点魔力值监控前端通用方法。
 */

/**
 *  构造插件 API  基础路径。
 */
export function pluginBase(pluginId) {
  return `plugin/${pluginId || 'SiteBonusMonitor'}`
}

/**
 *  标准化 API 响应：解开 {success, data, message} 包装。
 */
export function unwrapResponse(response) {
  if (!response) return null
  if (typeof response === 'object' && 'data' in response && response.success === false) {
    throw new Error(response.message || '请求失败')
  }
  if (response && typeof response === 'object' && 'data' in response && response.success === undefined) {
    // axios-style: {data, status, ...}
    return response.data
  }
  if (response && typeof response === 'object' && 'success' in response) {
    if (response.success === false) {
      throw new Error(response.message || '请求失败')
    }
    return response.data
  }
  return response
}

/**
 *  把秒级小时魔数渲染成字符串。
 */
export function formatHourlyBonus(value) {
  if (value === null || value === undefined) return '-'
  const sign = value >= 0 ? '+' : ''
  return `${sign}${Number(value).toFixed(4)}`
}

/**
 *  把 TB 数字格式化。
 */
export function formatTb(gb) {
  if (!gb) return '0 TB'
  return `${(Number(gb) / 1024).toFixed(2)} TB`
}
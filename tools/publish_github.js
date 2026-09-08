// 天神 GitHub 自动发布脚本（支持多版本）
// 用法: node tools/publish_github.js [--dry-run] [--tag v0.2] [--dir release/tianshen-v0.2] [--zip release/tianshen-v0.2.zip]
// 需要环境变量 GH_TOKEN（GitHub Personal Access Token，仅 repo 权限）
const fs = require('fs');
const path = require('path');

function argAfter(flag, def) {
  const i = process.argv.indexOf(flag);
  return i >= 0 ? process.argv[i + 1] : def;
}
const RELEASE_DIR = argAfter('--dir', 'release/tianshen-v0.2');
const ZIP_PATH = argAfter('--zip', 'release/tianshen-v0.2.zip');
const TAG = argAfter('--tag', 'v0.2');
const REPO_NAME = 'tianshen';
const API = 'https://api.github.com';

const RELEASE_META = {
  'v0.1': {
    name: '天神 v0.1：中文原生分词器（形）',
    body: '天神 v0.1：中文原生分词器（GPL-3.0）。\n\n- 64k 词表：token/字 0.938 反超 Qwen/GPT-4o，bits/字全场第一，整字保持率 1.0\n- 可切断拉丁挂件（默认关闭）\n- 完整复现指南见 RELEASE.md',
  },
  'v0.2': {
    name: '天神 v0.2：形+音合并词表',
    body: '天神 v0.2：形+音（GPL-3.0）。\n\n- 拼音数据层：GB2312 常用字 100% 覆盖，多音字 8,537 个\n- 64k 词表词级拼音标注（39,594 词，四级消歧流水线）\n- 多音消歧评测：天神 100% vs pypinyin 95.1%（185 词公开测试集）\n- 注音输出挂件 + 字/词级发声挂件（默认关闭）\n- 繁体同步标注 76,839 词条\n- 复现指南见 RELEASE.md',
  },
  'v0.3': {
    name: '天神 v0.3：形+音+意 真三维词空间',
    body: '天神 v0.3：形音意真三维词空间（GPL-3.0）。\n\n- 意平面 S（214 部首义素 + 1737 维深义关键词层）\n- 挂谷独立性检验：深义层被形⊕音解释 R²=0.0202 ✅ 真正新维度\n- 真三维组装 F⊕P⊕S2（3041 维，实测秩 2826，三平面正交）\n- 义近检索评测：S2 Hit@10=0.194 vs 形 0.139 vs 音 0.000（36 探针公开测试集）\n- 简体核心 12,468 字/31,466 词 + 繁体挂件 3,730（可插拔）\n- Token 经济学：token/字 0.762 全场第一；等知识量成本为 GPT-4o 的 1/38\n- 发布闸门 11/11 PASS（自动审计+自动校准+端到端贯通）+ 58 测试全绿\n- 三维演示 + 维度证书 + 复现指南见 RELEASE.md',
  },
};

function walk(dir, base = '') {
  const out = [];
  for (const name of fs.readdirSync(dir)) {
    const full = path.join(dir, name);
    const rel = base ? `${base}/${name}` : name;
    if (fs.statSync(full).isDirectory()) out.push(...walk(full, rel));
    else out.push(rel);
  }
  return out;
}

async function api(token, method, url, body) {
  const res = await fetch(url.startsWith('http') ? url : API + url, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      'User-Agent': 'tianshen-publisher/0.1',
      ...(body ? { 'Content-Type': 'application/json' } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  let json = null;
  try { json = JSON.parse(text); } catch { /* not json */ }
  if (!res.ok) {
    const err = new Error(`${method} ${url} -> ${res.status}: ${text.slice(0, 300)}`);
    err.status = res.status;
    err.json = json;
    throw err;
  }
  return json;
}

async function main() {
  const dryRun = process.argv.includes('--dry-run');
  const token = process.env.GH_TOKEN;

  const files = walk(RELEASE_DIR);
  console.log(`待发布文件: ${files.length} 个`);
  for (const f of files) console.log('  ' + f);

  if (dryRun || !token) {
    console.log(dryRun ? '[dry-run] 结束（未发起任何网络请求）' : '未设置 GH_TOKEN（需要你生成令牌后提供）');
    return;
  }

  // 1. 确认身份
  const me = await api(token, 'GET', '/user');
  const owner = me.login;
  console.log(`\n身份: ${owner}`);

  // 2. 创建仓库（已存在则继续）
  try {
    await api(token, 'POST', '/user/repos', {
      name: REPO_NAME,
      description: '天神（Tianshen）：中文原生分词器——中文第一公民 + 汉字原子性 + 字形通道（GPL-3.0）',
      homepage: '',
    });
    console.log(`仓库已创建: ${owner}/${REPO_NAME}`);
  } catch (e) {
    if (e.status === 422) console.log(`仓库已存在: ${owner}/${REPO_NAME}`);
    else if (e.status === 403) {
      console.error('令牌权限不足：创建仓库需要 Administration 权限，');
      console.error('或改用 classic 令牌并勾选 repo（参见 docs/06-发布指南.md 方案 C）。');
      throw e;
    } else throw e;
  }

  // 3. 空仓库引导：GitHub 不允许在完全空的仓库上建 blob，
  //    先用 Contents API 种一个初始提交，获得 main 分支的父提交。
  let parent = null;
  try {
    const ref = await api(token, 'GET', `/repos/${owner}/${REPO_NAME}/git/refs/heads/main`);
    parent = ref.object.sha;
    console.log('main 分支已存在，父提交:', parent.slice(0, 7));
  } catch {
    await api(token, 'PUT', `/repos/${owner}/${REPO_NAME}/contents/README.md`, {
      message: 'initial commit',
      content: Buffer.from('# tianshen\n').toString('base64'),
    });
    const ref2 = await api(token, 'GET', `/repos/${owner}/${REPO_NAME}/git/refs/heads/main`);
    parent = ref2.object.sha;
    console.log('已创建引导提交:', parent.slice(0, 7));
  }

  // 4. 逐个文件创建 blob
  console.log('上传文件中...');
  const tree = [];
  for (const rel of files) {
    const content = fs.readFileSync(path.join(RELEASE_DIR, rel));
    const blob = await api(token, 'POST', `/repos/${owner}/${REPO_NAME}/git/blobs`, {
      content: content.toString('base64'),
      encoding: 'base64',
    });
    tree.push({ path: rel, mode: '100644', type: 'blob', sha: blob.sha });
    process.stdout.write('.');
  }
  console.log('');

  // 5. 建树 + 提交 + 更新 main 分支
  const t = await api(token, 'POST', `/repos/${owner}/${REPO_NAME}/git/trees`, { tree });
  const c = await api(token, 'POST', `/repos/${owner}/${REPO_NAME}/git/commits`, {
    message: `天神 ${TAG}：中文原生词表（GPL-3.0）`,
    tree: t.sha,
    parents: [parent],
  });
  await api(token, 'PATCH', `/repos/${owner}/${REPO_NAME}/git/refs/heads/main`, { sha: c.sha });
  console.log('代码已推送至 main 分支');

  // 6. 发布 release + zip 附件
  const meta = RELEASE_META[TAG] || { name: `天神 ${TAG}`, body: `天神 ${TAG}（GPL-3.0）。` };
  const rel = await api(token, 'POST', `/repos/${owner}/${REPO_NAME}/releases`, {
    tag_name: TAG,
    name: meta.name,
    body: meta.body,
  });
  const zipBody = fs.readFileSync(ZIP_PATH);
  const zipName = path.basename(ZIP_PATH);
  const up = await fetch(
    `https://uploads.github.com/repos/${owner}/${REPO_NAME}/releases/${rel.id}/assets?name=${zipName}`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'User-Agent': 'tianshen-publisher/0.1',
        'Content-Type': 'application/octet-stream',
      },
      body: zipBody,
    }
  );
  if (!up.ok) throw new Error(`zip 上传失败: ${up.status} ${await up.text()}`);
  console.log(`\n✅ 发布完成: https://github.com/${owner}/${REPO_NAME}/releases/tag/${TAG}`);
  console.log('   建议：发布完成后立即吊销该令牌（GitHub → Settings → Developer settings → Tokens）。');
}

main().catch((e) => {
  console.error('发布失败:', e.message);
  process.exit(1);
});

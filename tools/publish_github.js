// 天神 v0.1 GitHub 自动发布脚本
// 用法: node tools/publish_github.js [--dry-run]
// 需要环境变量 GH_TOKEN（GitHub Personal Access Token，仅 repo 权限）
const fs = require('fs');
const path = require('path');

const RELEASE_DIR = 'release/tianshen-v0.1';
const ZIP_PATH = 'release/tianshen-v0.1.zip';
const REPO_NAME = 'tianshen';
const API = 'https://api.github.com';

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
    else throw e;
  }

  // 3. 逐个文件创建 blob
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

  // 4. 建树 + 提交 + 指向 main 分支
  const t = await api(token, 'POST', `/repos/${owner}/${REPO_NAME}/git/trees`, { tree });
  let parent = null;
  try {
    const ref = await api(token, 'GET', `/repos/${owner}/${REPO_NAME}/git/refs/heads/main`);
    parent = ref.object.sha;
  } catch { /* main 不存在，从空仓库开始 */ }
  const c = await api(token, 'POST', `/repos/${owner}/${REPO_NAME}/git/commits`, {
    message: '天神 v0.1：中文原生分词器（GPL-3.0）',
    tree: t.sha,
    ...(parent ? { parents: [parent] } : {}),
  });
  if (parent) {
    await api(token, 'PATCH', `/repos/${owner}/${REPO_NAME}/git/refs/heads/main`, { sha: c.sha });
  } else {
    await api(token, 'POST', `/repos/${owner}/${REPO_NAME}/git/refs`, { ref: 'refs/heads/main', sha: c.sha });
  }
  console.log('代码已推送至 main 分支');

  // 5. 发布 v0.1 release + zip 附件
  const rel = await api(token, 'POST', `/repos/${owner}/${REPO_NAME}/releases`, {
    tag_name: 'v0.1',
    name: '天神 v0.1',
    body: '天神 v0.1：中文原生分词器（GPL-3.0）。\n\n- 64k 词表：token/字 0.938 反超 Qwen/GPT-4o，bits/字全场第一，整字保持率 1.0\n- 可切断拉丁挂件（默认关闭）\n- 完整复现指南见 RELEASE.md',
  });
  const zipBody = fs.readFileSync(ZIP_PATH);
  const up = await fetch(
    `https://uploads.github.com/repos/${owner}/${REPO_NAME}/releases/${rel.id}/assets?name=tianshen-v0.1.zip`,
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
  console.log(`\n✅ 发布完成: https://github.com/${owner}/${REPO_NAME}`);
  console.log('   建议：发布完成后立即吊销该令牌（GitHub → Settings → Developer settings → Tokens）。');
}

main().catch((e) => {
  console.error('发布失败:', e.message);
  process.exit(1);
});

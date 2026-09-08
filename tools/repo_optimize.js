// 天神 GitHub 仓库优化脚本：门面元数据 + main 分支整树更新（不创建 release）。
// 用法: node tools/repo_optimize.js [--dir release/repo-main] [--dry-run]
// 需要环境变量 GH_TOKEN（GitHub classic token，仅 repo 权限）。
//
// 修订 1：GitHub git/trees 接口对 .github/ 路径返回 404（接口限制），
// 故 .github/ 下文件改走 Contents API（PUT），其余走树接口一次提交。
const fs = require('fs');
const path = require('path');

function argAfter(flag, def) {
  const i = process.argv.indexOf(flag);
  return i >= 0 ? process.argv[i + 1] : def;
}
const DIR = argAfter('--dir', 'release/repo-main');
const REPO_NAME = 'tianshen';
const API = 'https://api.github.com';

// 门面元数据（A 批）：描述 / 主题 / 主页；wiki 与 projects 关闭
const META = {
  description: '天神（Tianshen）：中文原生 AI——形·音·意真三维词空间（GPL-3.0）',
  homepage: 'https://github.com/tianshen999/tianshen',
  has_wiki: false,
  has_projects: false,
  topics: ['chinese', 'tokenizer', 'sentencepiece', 'pinyin', 'chinese-nlp', 'unigram', 'word-embeddings', 'gpl-3-0'],
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

async function api(token, method, url, body, tries = 4) {
  for (let i = 0; i < tries; i++) {
    try {
      const res = await fetch(url.startsWith('http') ? url : API + url, {
        method,
        headers: {
          Authorization: `Bearer ${token}`,
          'User-Agent': 'tianshen-optimizer/0.2',
          Accept: 'application/vnd.github+json',
          ...(body ? { 'Content-Type': 'application/json' } : {}),
        },
        body: body ? JSON.stringify(body) : undefined,
      });
      const text = await res.text();
      if (res.ok) {
        try { return JSON.parse(text); } catch { return text; }
      }
      const err = new Error(`${method} ${url} -> ${res.status}: ${text.slice(0, 300)}`);
      err.status = res.status;
      // 400/404/超时都重试一次（GitHub 瞬时故障与代理抖动）
      if (i === tries - 1) throw err;
    } catch (e) {
      if (i === tries - 1) throw e;
    }
    await new Promise((r) => setTimeout(r, 2000 * (i + 1)));
  }
}

async function main() {
  const dryRun = process.argv.includes('--dry-run');
  const token = process.env.GH_TOKEN;
  const files = walk(DIR);
  const treeFiles = files.filter((f) => !f.startsWith('.github/'));
  const githubFiles = files.filter((f) => f.startsWith('.github/'));
  console.log(`待更新文件: ${files.length} 个（树接口 ${treeFiles.length} + Contents 接口 ${githubFiles.length}）`);

  if (dryRun || !token) {
    console.log(dryRun ? '[dry-run] 结束（未发起任何网络请求）' : '未设置 GH_TOKEN（需要你生成令牌后提供）');
    return;
  }

  const me = await api(token, 'GET', '/user');
  const owner = me.login;
  console.log(`\n身份: ${owner}`);

  // A 批：门面元数据
  await api(token, 'PATCH', `/repos/${owner}/${REPO_NAME}`, META);
  console.log(`仓库元数据已更新: ${META.description}`);
  console.log(`  topics: ${META.topics.join(', ')}`);

  // B/C 批：整树推送（树接口：除 .github/ 外全部文件，一次提交）
  const ref = await api(token, 'GET', `/repos/${owner}/${REPO_NAME}/git/refs/heads/main`);
  const parent = ref.object.sha;
  console.log(`main 父提交: ${parent.slice(0, 7)}`);

  console.log('上传 blob 中...');
  const tree = [];
  for (const rel of treeFiles) {
    const content = fs.readFileSync(path.join(DIR, rel));
    const blob = await api(token, 'POST', `/repos/${owner}/${REPO_NAME}/git/blobs`, {
      content: content.toString('base64'),
      encoding: 'base64',
    });
    tree.push({ path: rel, mode: '100644', type: 'blob', sha: blob.sha });
    process.stdout.write('.');
  }
  console.log('');

  const t = await api(token, 'POST', `/repos/${owner}/${REPO_NAME}/git/trees`, { tree });
  const c = await api(token, 'POST', `/repos/${owner}/${REPO_NAME}/git/commits`, {
    message: '仓库优化：开箱可用 artifacts 布局 + 门面 + 云端闸门（GPL-3.0）',
    tree: t.sha,
    parents: [parent],
  });
  await api(token, 'PATCH', `/repos/${owner}/${REPO_NAME}/git/refs/heads/main`, { sha: c.sha });
  console.log(`树提交已推送: ${c.sha.slice(0, 7)}`);

  // .github/ 文件走 Contents API（git/trees 对 .github 路径返回 404 的规避）
  for (const rel of githubFiles) {
    const content = fs.readFileSync(path.join(DIR, rel));
    await api(token, 'PUT', `/repos/${owner}/${REPO_NAME}/contents/${rel}`, {
      message: `仓库优化：添加 ${rel}`,
      content: content.toString('base64'),
      branch: 'main',
    });
    console.log(`  Contents 已写入: ${rel}`);
  }

  console.log(`\n✅ 仓库优化完成: https://github.com/${owner}/${REPO_NAME}`);
  console.log('   建议：完成后立即吊销该令牌（GitHub → Settings → Developer settings → Tokens）。');
}

main().catch((e) => {
  console.error('优化失败:', e.message);
  process.exit(1);
});

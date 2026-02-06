// --- Tabs ---
function showTab(name) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
    document.getElementById('tab-' + name).classList.add('active');
    document.getElementById('nav-' + name).classList.add('active');

    if (name === 'costs') loadCosts();
    if (name === 'campaigns') loadCampaigns();
    if (name === 'settings') { loadSmartStatus(); loadTemplates(); }
}

// --- Toast ---
function toast(msg, type) {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.className = 'toast ' + (type || '');
    setTimeout(() => el.classList.add('hidden'), 3000);
}

// --- API helpers ---
async function api(url, opts) {
    const res = await fetch(url, {
        headers: { 'Content-Type': 'application/json' },
        ...opts,
        body: opts && opts.body ? JSON.stringify(opts.body) : undefined,
    });
    return res.json();
}

// --- Pipeline ---
async function startPipeline() {
    const url = document.getElementById('pipeline-url').value.trim();
    if (!url) { toast('Cole a URL do video', 'error'); return; }

    const btn = document.getElementById('btn-pipeline');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>Gerando...';

    const statusDiv = document.getElementById('pipeline-status');
    const logsDiv = document.getElementById('pipeline-logs');
    const resultDiv = document.getElementById('pipeline-result');
    statusDiv.classList.remove('hidden');
    logsDiv.textContent = 'Iniciando pipeline...\n';
    resultDiv.innerHTML = '';

    const data = await api('/api/pipeline', {
        method: 'POST',
        body: {
            url: url,
            clips: parseInt(document.getElementById('pipeline-clips').value) || 5,
            category: document.getElementById('pipeline-category').value || 'FAMOSOS',
            headline: document.getElementById('pipeline-headline').value || null,
            campaign_id: parseInt(document.getElementById('pipeline-campaign').value) || null,
            smart: document.getElementById('pipeline-smart').checked,
        },
    });

    if (data.error) {
        logsDiv.textContent += 'ERRO: ' + data.error + '\n';
        btn.disabled = false;
        btn.textContent = 'Gerar Clipes';
        return;
    }

    // Poll job status
    const jobId = data.job_id;
    const poll = setInterval(async () => {
        const job = await api('/api/jobs/' + jobId);
        logsDiv.textContent = job.logs.join('\n') + '\n';
        logsDiv.scrollTop = logsDiv.scrollHeight;

        if (job.status === 'done') {
            clearInterval(poll);
            btn.disabled = false;
            btn.textContent = 'Gerar Clipes';

            const r = job.result;
            resultDiv.innerHTML = '<div style="margin-top:12px;color:var(--green);font-weight:600">' +
                r.clips_count + ' clipes gerados!</div>';
            if (r.clips) {
                resultDiv.innerHTML += '<table><tr><th>#</th><th>Arquivo</th><th>Headline</th></tr>' +
                    r.clips.map((c, i) =>
                        '<tr><td>' + (i+1) + '</td><td style="font-size:12px">' +
                        c.path + '</td><td>' + (c.headline || '-') + '</td></tr>'
                    ).join('') + '</table>';
            }
            toast('Pipeline concluido!', 'success');
        } else if (job.status === 'error') {
            clearInterval(poll);
            btn.disabled = false;
            btn.textContent = 'Gerar Clipes';
            logsDiv.textContent += '\nERRO: ' + job.error;
            toast('Erro no pipeline', 'error');
        }
    }, 2000);
}

// --- Campaigns ---
async function loadCampaigns() {
    const data = await api('/api/campaigns');
    const list = document.getElementById('campaigns-list');

    if (!data.campaigns || data.campaigns.length === 0) {
        list.innerHTML = '<p class="muted">Nenhuma campanha criada ainda.</p>';
        return;
    }

    list.innerHTML = data.campaigns.map(c => {
        const clips = c.clips.map(cl => {
            const links = Object.entries(cl.posted_links || {}).map(([p,l]) => p + ': ' + l).join(', ');
            const badge = cl.submitted_to_platform
                ? '<span class="badge badge-green">Submetido</span>'
                : links
                    ? '<span class="badge badge-yellow">Postado</span>'
                    : '<span class="badge badge-red">Pendente</span>';
            return '<div style="margin:4px 0">' + badge + ' Clip #' + cl.id +
                (links ? ' - ' + links : '') + '</div>';
        }).join('');

        return '<div class="campaign-item">' +
            '<h4>#' + c.id + ' ' + c.name + '</h4>' +
            '<div class="meta">' + c.influencer + ' | R$' + c.pay_per_1k_views + '/1k views | Min: ' + c.min_views + ' views</div>' +
            '<div class="clips">' + (clips || '<span class="muted">Nenhum clipe ainda</span>') + '</div>' +
            '</div>';
    }).join('');
}

async function createCampaign() {
    const data = await api('/api/campaigns', {
        method: 'POST',
        body: {
            name: document.getElementById('camp-name').value,
            influencer: document.getElementById('camp-influencer').value,
            pay: parseFloat(document.getElementById('camp-pay').value) || 0,
            min_views: parseInt(document.getElementById('camp-minviews').value) || 10000,
        },
    });
    toast('Campanha #' + data.id + ' criada!', 'success');
    loadCampaigns();
}

async function addLink() {
    const campId = parseInt(document.getElementById('link-campaign').value);
    const clipId = parseInt(document.getElementById('link-clip').value);
    const platform = document.getElementById('link-platform').value;
    const link = document.getElementById('link-url').value;

    if (!campId || !clipId || !link) { toast('Preencha todos os campos', 'error'); return; }

    await api('/api/campaigns/' + campId + '/link', {
        method: 'POST',
        body: { clip_id: clipId, platform: platform, link: link },
    });
    toast('Link registrado!', 'success');
    document.getElementById('link-url').value = '';
    loadCampaigns();
}

// --- Research ---
async function startResearch() {
    const influencer = document.getElementById('research-influencer').value.trim();
    if (!influencer) { toast('Digite o nome do influenciador', 'error'); return; }

    const btn = document.getElementById('btn-research');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>Pesquisando...';

    const statusDiv = document.getElementById('research-status');
    const resultPre = document.getElementById('research-result');
    statusDiv.classList.remove('hidden');
    resultPre.textContent = 'Pesquisando ' + influencer + '...\nIsso pode levar alguns minutos.\n';

    const data = await api('/api/research', {
        method: 'POST',
        body: { influencer: influencer },
    });

    const jobId = data.job_id;
    const poll = setInterval(async () => {
        const job = await api('/api/jobs/' + jobId);
        resultPre.textContent = job.logs.join('\n') + '\n';

        if (job.status === 'done') {
            clearInterval(poll);
            btn.disabled = false;
            btn.textContent = 'Pesquisar';
            resultPre.textContent = job.result.report;
            toast('Pesquisa concluida!', 'success');
        } else if (job.status === 'error') {
            clearInterval(poll);
            btn.disabled = false;
            btn.textContent = 'Pesquisar';
            resultPre.textContent += '\nERRO: ' + job.error;
        }
    }, 2000);
}

// --- Costs ---
async function loadCosts() {
    const data = await api('/api/costs');

    document.getElementById('cost-total-brl').textContent = 'R$' + (data.total_brl || 0).toFixed(2);
    document.getElementById('cost-total-calls').textContent = data.total_calls || 0;
    document.getElementById('cost-total-usd').textContent = 'US$' + (data.total_usd || 0).toFixed(4);

    // By operation
    const opDiv = document.getElementById('costs-by-op');
    const ops = data.by_operation || {};
    if (Object.keys(ops).length === 0) {
        opDiv.innerHTML = '<p class="muted">Nenhuma chamada registrada ainda.</p>';
    } else {
        opDiv.innerHTML = '<table><tr><th>Operacao</th><th>Chamadas</th><th>Custo</th></tr>' +
            Object.entries(ops).map(([op, s]) =>
                '<tr><td>' + op + '</td><td>' + s.count + '</td><td>R$' + s.brl.toFixed(4) + '</td></tr>'
            ).join('') + '</table>';
    }

    // Recent
    const recentDiv = document.getElementById('costs-recent');
    if (!data.recent || data.recent.length === 0) {
        recentDiv.innerHTML = '<p class="muted">Nenhuma chamada ainda.</p>';
    } else {
        recentDiv.innerHTML = '<table><tr><th>Data</th><th>Operacao</th><th>Tokens</th><th>Custo</th></tr>' +
            data.recent.reverse().map(c =>
                '<tr><td style="font-size:12px">' + (c.timestamp || '').slice(0,19).replace('T',' ') +
                '</td><td>' + c.operation +
                '</td><td style="font-size:12px">' + c.input_tokens + ' in / ' + c.output_tokens + ' out' +
                '</td><td>R$' + c.cost_brl.toFixed(4) + '</td></tr>'
            ).join('') + '</table>';
    }
}

async function calculateROI() {
    const revenue = parseFloat(document.getElementById('roi-revenue').value) || 0;
    const data = await api('/api/costs/roi', { method: 'POST', body: { revenue: revenue } });

    const div = document.getElementById('roi-result');
    const cls = data.worth_it ? 'roi-positive' : 'roi-negative';
    const emoji = data.worth_it ? 'Compensando!' : 'NAO compensando';
    div.innerHTML = '<div style="margin-top:12px">' +
        '<div class="' + cls + '">' + emoji + '</div>' +
        '<table style="margin-top:8px">' +
        '<tr><td>Receita</td><td>R$' + data.revenue.toFixed(2) + '</td></tr>' +
        '<tr><td>Custo API</td><td>R$' + data.cost.toFixed(2) + '</td></tr>' +
        '<tr><td>Lucro</td><td>R$' + data.profit.toFixed(2) + '</td></tr>' +
        '<tr><td>ROI</td><td>' + data.roi_percent.toFixed(0) + '%</td></tr>' +
        '</table></div>';
}

// --- Settings ---
async function loadSmartStatus() {
    const data = await api('/api/smart');
    document.getElementById('smart-toggle').checked = data.enabled;
    document.getElementById('smart-status-text').textContent = data.enabled ? 'LIGADO' : 'DESLIGADO';

    if (data.api_key_set) {
        document.getElementById('smart-description').textContent =
            'API Key configurada (' + data.api_key_preview + '). ' +
            (data.enabled ? 'IA ativa em todos os pipelines.' : 'IA desligada. Use --smart pontualmente ou ligue aqui.');
    } else {
        document.getElementById('smart-description').textContent =
            'API Key NAO configurada. Va em Config > API Keys para configurar.';
    }
}

async function toggleSmart() {
    const enabled = document.getElementById('smart-toggle').checked;
    const data = await api('/api/smart', { method: 'POST', body: { enabled: enabled } });
    document.getElementById('smart-status-text').textContent = enabled ? 'LIGADO' : 'DESLIGADO';
    toast(data.message, 'success');
}

async function loadTemplates() {
    const templates = await api('/api/templates');
    const list = document.getElementById('templates-list');
    list.innerHTML = templates.map(t =>
        '<div class="template-item"><span class="template-name">' + t.name + '</span><span class="muted">' + t.description + '</span></div>'
    ).join('');
}

async function saveEnv() {
    const keys = {};
    const anthropic = document.getElementById('env-anthropic').value.trim();
    const twitchId = document.getElementById('env-twitch-id').value.trim();
    const twitchSecret = document.getElementById('env-twitch-secret').value.trim();

    if (anthropic) keys.ANTHROPIC_API_KEY = anthropic;
    if (twitchId) keys.TWITCH_CLIENT_ID = twitchId;
    if (twitchSecret) keys.TWITCH_CLIENT_SECRET = twitchSecret;

    if (Object.keys(keys).length === 0) { toast('Nenhuma chave preenchida', 'error'); return; }

    await api('/api/env', { method: 'POST', body: keys });
    toast('Keys salvas!', 'success');
    document.getElementById('env-status').textContent = 'Salvo: ' + Object.keys(keys).join(', ');

    // Limpa campos de senha
    document.getElementById('env-anthropic').value = '';
    document.getElementById('env-twitch-secret').value = '';

    loadSmartStatus();
}

// --- Init ---
document.addEventListener('DOMContentLoaded', () => {
    loadSmartStatus();
});

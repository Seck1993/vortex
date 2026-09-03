function googleTranslateElementInit() {
            new google.translate.TranslateElement({
                pageLanguage: 'pt',
                includedLanguages: 'en,es,fr,ru,ja,ko,zh-CN,tl',
                layout: google.translate.TranslateElement.InlineLayout.SIMPLE
            }, 'google_translate_element');
        }

        /* --- SELETOR DE IDIOMA CUSTOMIZADO (COM BANDEIRAS) --- */
        const BANDEIRAS_IDIOMA = {
            pt: '🇧🇷', en: '🇺🇸', es: '🇪🇸', fr: '🇫🇷', ru: '🇷🇺',
            ja: '🇯🇵', ko: '🇰🇷', 'zh-CN': '🇨🇳', tl: '🇵🇭'
        };

        function toggleSeletorIdioma() {
            document.getElementById('painelIdiomas').classList.toggle('aberto');
        }

        function definirIdioma(codigo) {
            const dominio = window.location.hostname;
            if (codigo === 'pt') {
                document.cookie = 'googtrans=; path=/; expires=Thu, 01 Jan 1970 00:00:00 UTC';
                document.cookie = 'googtrans=; path=/; domain=' + dominio + '; expires=Thu, 01 Jan 1970 00:00:00 UTC';
            } else {
                const valor = '/pt/' + codigo;
                document.cookie = 'googtrans=' + valor + '; path=/;';
                document.cookie = 'googtrans=' + valor + '; path=/; domain=' + dominio + ';';
            }
            window.location.reload();
        }

        function aplicarIdiomaAtivoNoBotao() {
            const match = document.cookie.match(/googtrans=\/pt\/([a-zA-Z-]+)/);
            const codigo = match ? match[1] : 'pt';
            const bandeiraEl = document.getElementById('bandeiraAtual');
            if (bandeiraEl) bandeiraEl.innerText = BANDEIRAS_IDIOMA[codigo] || '🇧🇷';
        }
        document.addEventListener('DOMContentLoaded', aplicarIdiomaAtivoNoBotao);

        document.addEventListener('click', (e) => {
            const seletor = document.getElementById('seletorIdioma');
            const painel = document.getElementById('painelIdiomas');
            if (seletor && painel && !seletor.contains(e.target)) painel.classList.remove('aberto');
        });

        function isAdmin() { return document.getElementById('app-root').dataset.isAdmin === 'true'; }
        function isLoggedIn() { return document.getElementById('app-root').dataset.loggedIn === 'true'; }

        function abrirModal(id) { document.getElementById(id).style.display = 'flex'; }
        function fecharModal(id) { document.getElementById(id).style.display = 'none'; }
        function fecharModalEAtualizar() { fecharModal('modalRoletaMeme'); atualizarDados(); }

        /* --- SISTEMA DE TOASTS (substitui alert()) --- */
        function mostrarToast(mensagem, tipo = 'info', duracao = 4500) {
            const container = document.getElementById('toastContainer');
            if (!container) { console.warn(mensagem); return; }
            const icones = { sucesso: '✓', erro: '✖', aviso: '⚠', info: 'ℹ' };
            const toast = document.createElement('div');
            toast.className = `toast toast-${tipo}`;
            toast.innerHTML = `<span class="toast-icon">${icones[tipo] || icones.info}</span><span class="toast-msg"></span>`;
            toast.querySelector('.toast-msg').textContent = mensagem;
            container.appendChild(toast);
            requestAnimationFrame(() => requestAnimationFrame(() => toast.classList.add('show')));
            setTimeout(() => {
                toast.classList.remove('show');
                toast.addEventListener('transitionend', () => toast.remove(), { once: true });
                setTimeout(() => toast.remove(), 500);
            }, duracao);
        }

        /* --- ATUALIZAÇÃO DE DADOS SEM RECARREGAR A PÁGINA --- */
        async function atualizarDados() {
            try {
                const resp = await fetch(window.location.pathname, { cache: 'no-store' });
                if (!resp.ok) throw new Error('status ' + resp.status);
                const html = await resp.text();
                const doc = new DOMParser().parseFromString(html, 'text/html');
                const novoRoot = doc.getElementById('app-root');
                const atualRoot = document.getElementById('app-root');
                if (!novoRoot || !atualRoot) throw new Error('app-root ausente na resposta');

                // Preserva o widget do Google Translate (não sobrevive a um innerHTML novo)
                const translateAtual = document.getElementById('google_translate_element');
                const abaAtivaBtn = document.querySelector('.tab-btn.active');
                const abaAtivaIndice = abaAtivaBtn ? Array.from(abaAtivaBtn.parentElement.children).indexOf(abaAtivaBtn) : -1;
                const abaAtivaId = document.querySelector('.tab-content.active') ? document.querySelector('.tab-content.active').id : null;

                atualRoot.dataset.isAdmin = novoRoot.dataset.isAdmin;
                atualRoot.dataset.loggedIn = novoRoot.dataset.loggedIn;
                atualRoot.innerHTML = novoRoot.innerHTML;

                const translateNovo = document.getElementById('google_translate_element');
                if (translateAtual && translateNovo) translateNovo.replaceWith(translateAtual);
                aplicarIdiomaAtivoNoBotao();
                configurarTodasPaginacoes();

                // Restaura a aba selecionada e recalcula overlays de CP (Mega/Titã)
                if (abaAtivaId && abaAtivaIndice >= 0 && document.getElementById(abaAtivaId)) {
                    const novoBtn = document.querySelectorAll('.tab-btn')[abaAtivaIndice];
                    if (novoBtn) { trocarAba(abaAtivaId, novoBtn); return; }
                }
                aplicarLinhasPoder();
            } catch (e) {
                console.error('Falha ao atualizar dados:', e);
                mostrarToast('Não foi possível atualizar os dados automaticamente. Recarregando...', 'erro');
                setTimeout(() => window.location.reload(), 1200);
            }
        }

        /* Atualiza só um elemento (por id) a partir do HTML mais recente do servidor,
           sem tocar no resto da página — usado dentro de modais que precisam continuar
           abertos (ex: gerenciamento de Staff) enquanto os dados são sincronizados. */
        async function atualizarElementoParcial(elementId) {
            const resp = await fetch(window.location.pathname, { cache: 'no-store' });
            if (!resp.ok) throw new Error('status ' + resp.status);
            const html = await resp.text();
            const doc = new DOMParser().parseFromString(html, 'text/html');
            const novo = doc.getElementById(elementId);
            const atual = document.getElementById(elementId);
            if (novo && atual) atual.innerHTML = novo.innerHTML;
        }

        /* --- CRONÔMETRO DIGITAL --- */
        function atualizarCronometros() {
            const timerDisplay = document.getElementById('timerDisplay');
            if (!timerDisplay) return;

            const prazoRaw = timerDisplay.getAttribute('data-prazo');
            if (!prazoRaw || prazoRaw.trim() === "") {
                timerDisplay.innerText = "SEM TEMPO LIMITE";
                timerDisplay.style.fontSize = "26px";
                return;
            }

            const prazo = parseFloat(prazoRaw);
            if (isNaN(prazo)) {
                timerDisplay.innerText = "ENCERRADO";
                timerDisplay.style.color = "var(--neon-red)";
                return;
            }

            const agora = Date.now();
            const diff = prazo - agora;

            if (diff <= 0) {
                timerDisplay.innerText = "TEMPO ENCERRADO";
                timerDisplay.style.color = "var(--neon-red)";
                document.querySelectorAll('.btn-apostar').forEach(b => b.style.display = 'none');
            } else {
                const horas = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
                const min = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
                const seg = Math.floor((diff % (1000 * 60)) / 1000);
                timerDisplay.innerText = `${horas.toString().padStart(2, '0')}:${min.toString().padStart(2, '0')}:${seg.toString().padStart(2, '0')}`;
                timerDisplay.style.color = "var(--neon-green)";
            }
        }
        setInterval(atualizarCronometros, 1000);
        document.addEventListener('DOMContentLoaded', atualizarCronometros);

        async function fazerLogin() {
            const senha = document.getElementById('senhaAdmin').value;
            const btn = document.querySelector('#modalLogin .btn:nth-child(2)');
            btn.innerText = 'Processando...';
            try {
                const response = await fetch('/api/login', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ senha: senha })
                });
                if (response.ok) { fecharModal('modalLogin'); document.getElementById('senhaAdmin').value = ''; btn.innerText = 'Autenticar'; await atualizarDados(); mostrarToast('Acesso autorizado!', 'sucesso'); }
                else { mostrarToast('Acesso Negado: Credencial Inválida', 'erro'); btn.innerText = 'Autenticar'; }
            } catch (e) { mostrarToast('Falha de conexão com o servidor matriz.', 'erro'); btn.innerText = 'Autenticar'; }
        }

        async function fazerLogout() {
            try {
                const response = await fetch('/api/logout', { method: 'POST' });
                if (response.ok) { await atualizarDados(); mostrarToast('Sessão encerrada.', 'info'); }
            } catch (e) { mostrarToast('Erro de conexão', 'erro'); }
        }

        /* --- LOGICA DE RÉGUAS MEGA E TITÃ E FILTROS --- */
        function aplicarLinhasPoder() {
            const cpMega = parseInt(document.getElementById('inputMegaCP').value) || 0;
            const cpTita = parseInt(document.getElementById('inputTitaCP').value) || 0;

            // Remove clones antigos e reseta brilhos
            document.querySelectorAll('.linha-mega, .mega-clone, .linha-tita, .tita-clone, .banner-destaque').forEach(el => el.remove());
            document.querySelectorAll('tr').forEach(el => el.classList.remove('mega-glow', 'tita-glow'));

            // ================= ABA RANKING (MANTÉM COMO ESTAVA) =================
            const tbodyRanking = document.querySelector(`#abaRanking tbody`);
            if (tbodyRanking) {
                const linhasOriginais = Array.from(tbodyRanking.querySelectorAll('tr:not(.linha-vazia)'));
                if (!(linhasOriginais.length === 1 && linhasOriginais[0].querySelector('td') && linhasOriginais[0].querySelector('td').colSpan > 5)) {
                    let clonesMega = [];
                    let clonesTita = [];

                    linhasOriginais.forEach(linha => {
                        const cp = parseInt(linha.getAttribute('data-poder')) || 0;
                        if (cp >= cpMega && cpMega > 0) {
                            linha.classList.add('mega-glow');
                            let clone = linha.cloneNode(true);
                            clone.classList.add('mega-clone');
                            clone.querySelectorAll('.input-edit, select, input[type="checkbox"]').forEach(el => {
                                el.disabled = true; el.style.opacity = '0.6'; el.title = "Visualização Mega.";
                            });
                            let colRank = clone.querySelector('.rank-display');
                            if (colRank) colRank.innerHTML = '⭐';
                            clonesMega.push({ element: clone, cp: cp });
                        } else if (cp >= cpTita && cpTita > 0) {
                            linha.classList.add('tita-glow');
                            let clone = linha.cloneNode(true);
                            clone.classList.add('tita-clone');
                            clone.querySelectorAll('.input-edit, select, input[type="checkbox"]').forEach(el => {
                                el.disabled = true; el.style.opacity = '0.6'; el.title = "Visualização Titã.";
                            });
                            let colRank = clone.querySelector('.rank-display');
                            if (colRank) colRank.innerHTML = '⚔️';
                            clonesTita.push({ element: clone, cp: cp });
                        }
                    });

                    if (clonesTita.length > 0) {
                        clonesTita.sort((a, b) => b.cp - a.cp);
                        const trDivisorTita = document.createElement('tr');
                        trDivisorTita.className = 'linha-tita';
                        trDivisorTita.innerHTML = `<td colspan="100"><div style="display: flex; align-items: center; justify-content: center; gap: 20px; padding: 15px 0;"><span style="flex: 1; height: 2px; background: linear-gradient(90deg, transparent, var(--blue-tita));"></span><span style="color: var(--blue-tita); text-shadow: 0 0 15px var(--blue-tita); font-size: 22px; font-weight: bold; letter-spacing: 5px;">⚔️ TITÃS ⚔️</span><span style="flex: 1; height: 2px; background: linear-gradient(270deg, transparent, var(--blue-tita));"></span></div></td>`;
                        tbodyRanking.insertBefore(trDivisorTita, tbodyRanking.firstChild);
                        clonesTita.reverse().forEach(cloneObj => { tbodyRanking.insertBefore(cloneObj.element, tbodyRanking.firstChild); });
                    }

                    if (clonesMega.length > 0) {
                        clonesMega.sort((a, b) => b.cp - a.cp);
                        const trDivisorMega = document.createElement('tr');
                        trDivisorMega.className = 'linha-mega';
                        trDivisorMega.innerHTML = `<td colspan="100"><div style="display: flex; align-items: center; justify-content: center; gap: 20px; padding: 15px 0;"><span style="flex: 1; height: 2px; background: linear-gradient(90deg, transparent, var(--gold-mega));"></span><span style="color: var(--gold-mega); text-shadow: 0 0 15px var(--gold-mega); font-size: 22px; font-weight: bold; letter-spacing: 5px;">⚡ MEGA PLAYERS ⚡</span><span style="flex: 1; height: 2px; background: linear-gradient(270deg, transparent, var(--gold-mega));"></span></div></td>`;
                        tbodyRanking.insertBefore(trDivisorMega, tbodyRanking.firstChild);
                        clonesMega.reverse().forEach(cloneObj => { tbodyRanking.insertBefore(cloneObj.element, tbodyRanking.firstChild); });
                    }
                }
            }

            // ================= ABA CLASSES (NOVO VISUAL BANNERS) =================
            const tbodyClasses = document.querySelector(`#abaClasses tbody`);
            const containerBanners = document.getElementById('containerBannersClasses');

            if (tbodyClasses && containerBanners) {
                containerBanners.innerHTML = '';
                const linhasClasses = Array.from(tbodyClasses.querySelectorAll('tr:not(.linha-vazia)'));
                let megasHTML = '';
                let titasHTML = '';

                linhasClasses.forEach(linha => {
                    const cp = parseInt(linha.getAttribute('data-poder')) || 0;

                    const nomeCell = linha.cells[1].innerText.trim();
                    const selectElement = linha.querySelector('.edit-classe');
                    const hiddenClasse = linha.querySelector('input[type="hidden"].edit-classe');
                    const spanClasse = linha.querySelector('span.edit-classe');

                    let classeStr = "Indefinida";
                    // .edit-classe pode ser um <select> (edição inline) ou um <input hidden>
                    // (exibição somente leitura); só o <select> tem .options.
                    if(selectElement && selectElement.tagName === 'SELECT') {
                        classeStr = selectElement.options[selectElement.selectedIndex]?.text || "Indefinida";
                    } else if(hiddenClasse) {
                        classeStr = hiddenClasse.value || "Indefinida";
                    } else if(spanClasse) {
                        classeStr = spanClasse.innerText || "Indefinida";
                    }

                    if (cp >= cpMega && cpMega > 0) {
                        linha.classList.add('mega-glow');
                        megasHTML += `
                            <div class="banner-destaque banner-mega">
                                <div class="icone">⭐</div>
                                <div class="info">
                                    <div class="nome">${nomeCell}</div>
                                    <div class="classe">${classeStr}</div>
                                    <div class="cp">${cp.toLocaleString('pt-BR')} CP</div>
                                </div>
                            </div>`;
                    } else if (cp >= cpTita && cpTita > 0) {
                        linha.classList.add('tita-glow');
                        titasHTML += `
                            <div class="banner-destaque banner-tita">
                                <div class="icone">⚔️</div>
                                <div class="info">
                                    <div class="nome">${nomeCell}</div>
                                    <div class="classe">${classeStr}</div>
                                    <div class="cp">${cp.toLocaleString('pt-BR')} CP</div>
                                </div>
                            </div>`;
                    }
                });

                if (megasHTML !== '') {
                    containerBanners.innerHTML += `<div style="width: 100%;"><h3 style="color: var(--gold-mega); text-align: center; text-shadow: 0 0 10px var(--gold-mega); margin-top: 0;">⚡ MEGA PLAYERS ⚡</h3><div style="display: flex; gap: 15px; justify-content: center; flex-wrap: wrap; margin-bottom: 25px;">${megasHTML}</div></div>`;
                }
                if (titasHTML !== '') {
                    containerBanners.innerHTML += `<div style="width: 100%;"><h3 style="color: var(--blue-tita); text-align: center; text-shadow: 0 0 10px var(--blue-tita); margin-top: 10px;">⚔️ TITÃS ⚔️</h3><div style="display: flex; gap: 15px; justify-content: center; flex-wrap: wrap; margin-bottom: 25px;">${titasHTML}</div></div>`;
                }
            }
        }
        document.addEventListener('DOMContentLoaded', () => { aplicarLinhasPoder(); });

        /* --- PAGINAÇÃO (CLIENTE) DAS TABELAS DE HISTÓRICO --- */
        const ITENS_POR_PAGINA_HISTORICO = 10;
        const estadoPaginacao = {};

        function configurarPaginacao(tbodyId, controlesId, porPagina = ITENS_POR_PAGINA_HISTORICO) {
            const tbody = document.getElementById(tbodyId);
            const controles = document.getElementById(controlesId);
            if (!tbody || !controles) return;

            const linhas = Array.from(tbody.querySelectorAll('tr.linha-dado'));
            const totalPaginas = Math.max(1, Math.ceil(linhas.length / porPagina));
            let paginaAtual = estadoPaginacao[tbodyId] || 1;
            if (paginaAtual > totalPaginas) paginaAtual = totalPaginas;
            estadoPaginacao[tbodyId] = paginaAtual;

            linhas.forEach((tr, i) => {
                const dentroDaPagina = i >= (paginaAtual - 1) * porPagina && i < paginaAtual * porPagina;
                tr.style.display = dentroDaPagina ? '' : 'none';
            });

            if (linhas.length <= porPagina) {
                controles.innerHTML = '';
                return;
            }

            controles.innerHTML = `
                <button ${paginaAtual === 1 ? 'disabled' : ''} onclick="irParaPagina('${tbodyId}', '${controlesId}', ${paginaAtual - 1}, ${porPagina})">← Anterior</button>
                <span class="pagina-atual">Página ${paginaAtual} de ${totalPaginas}</span>
                <button ${paginaAtual === totalPaginas ? 'disabled' : ''} onclick="irParaPagina('${tbodyId}', '${controlesId}', ${paginaAtual + 1}, ${porPagina})">Próxima →</button>
            `;
        }

        function irParaPagina(tbodyId, controlesId, pagina, porPagina) {
            estadoPaginacao[tbodyId] = pagina;
            configurarPaginacao(tbodyId, controlesId, porPagina);
        }

        function configurarTodasPaginacoes() {
            configurarPaginacao('bodyHistoricoSorteios', 'paginacaoHistoricoSorteios');
            configurarPaginacao('bodyHistoricoMeme', 'paginacaoHistoricoMeme');
            configurarPaginacao('bodyMembros', 'paginacaoMembros');
        }
        document.addEventListener('DOMContentLoaded', configurarTodasPaginacoes);

        function trocarAba(abaId, elementoBtn) {
            document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            document.getElementById(abaId).classList.add('active');
            elementoBtn.classList.add('active');
            aplicarLinhasPoder();
        }

        function filtrarTabelaClasses() {
            const filtro = document.getElementById('filtroClasse').value;
            const linhas = document.querySelectorAll('#abaClasses tbody tr:not(.linha-mega):not(.linha-tita)');
            let rankVisivel = 1;
            linhas.forEach(linha => {
                if (linha.querySelector('td').colSpan > 10) return;
                const selectElement = linha.querySelector('.edit-classe');
                const classeAtribuida = selectElement ? selectElement.value : "";
                if (filtro === "Todas" || classeAtribuida === filtro) {
                    linha.style.display = "";
                    if (!linha.classList.contains('mega-clone') && !linha.classList.contains('tita-clone')) { linha.querySelector('.rank-display').innerText = rankVisivel++; }
                } else { linha.style.display = "none"; }
            });
            document.querySelectorAll('#abaClasses .linha-mega, #abaClasses .linha-tita').forEach(el => el.style.display = filtro === "Todas" ? "" : "none");
        }

        /* --- LÓGICA DE EVENTOS (BANNER E APOSTAS) --- */
        function adicionarCampoItem() {
            const container = document.getElementById('listaItensCriacao');
            const index = container.children.length + 1;
            const html = `
                <div style="display: flex; gap: 10px; margin-bottom: 10px; align-items: center;">
                    <input type="text" class="input-edit item-nome-novo" placeholder="Nome do Item ${index}" style="flex: 2; text-align: left;">
                    <select class="input-edit item-restricao-novo" style="flex: 1;">
                        <option value="Todos">Todos</option>
                        <option value="Titã">Apenas Titãs+</option>
                        <option value="Mega">Apenas Megas</option>
                    </select>
                    <input type="number" class="input-edit item-pontos-novo" placeholder="Pontos (100%)" value="100" style="flex: 1;">
                </div>
            `;
            container.insertAdjacentHTML('beforeend', html);
        }

        async function salvarNovoEvento() {
            const titulo = document.getElementById('tituloEvento').value;
            const minutosInput = document.getElementById('prazoEvento').value;
            const minutos = parseInt(minutosInput) || 60;

            const prazoTimestamp = Date.now() + (minutos * 60000);

            let itens = [];
            document.querySelectorAll('.item-nome-novo').forEach((input, i) => {
                const maxPts = document.querySelectorAll('.item-pontos-novo')[i].value;
                const restricao = document.querySelectorAll('.item-restricao-novo')[i].value;
                if(input.value.trim()) itens.push({ nome: input.value, max_pontos: maxPts, restricao: restricao });
            });
            if (itens.length === 0) return mostrarToast("Adicione pelo menos um item!", 'aviso');

            const response = await fetch('/api/publicar-banner', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ titulo: titulo, prazo: prazoTimestamp.toString(), itens: itens })
            });
            if(response.ok) { fecharModal('modalCriarEvento'); await atualizarDados(); mostrarToast('Banner de sorteio publicado!', 'sucesso'); }
            else { mostrarToast('Falha ao publicar o banner.', 'erro'); }
        }

        async function encerrarEvento() {
            if(!confirm("Encerrar o banner sumirá com ele da tela. Continuar?")) return;
            await fetch('/api/encerrar-banner', {method: 'POST'});
            await atualizarDados();
            mostrarToast('Evento encerrado. Pontos estornados aos jogadores.', 'info');
        }

        function abrirModalEditarPersonagem(jogadorId, nome, level, poder) {
            document.getElementById('editPersonagemId').value = jogadorId;
            document.getElementById('tituloEditarPersonagem').innerText = 'Atualizar: ' + nome;
            document.getElementById('editPersonagemLevel').value = level;
            document.getElementById('editPersonagemPoder').value = poder;
            abrirModal('modalEditarPersonagem');
        }

        async function salvarEdicaoPersonagem() {
            const jogadorId = document.getElementById('editPersonagemId').value;
            const level = document.getElementById('editPersonagemLevel').value;
            const poder = document.getElementById('editPersonagemPoder').value;

            try {
                const response = await fetch('/api/editar-jogadores', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ jogadores: [{ id: jogadorId, level: level, poder_combate: poder }] })
                });
                if (response.ok) {
                    fecharModal('modalEditarPersonagem');
                    await atualizarDados();
                    mostrarToast('Personagem atualizado com sucesso!', 'sucesso');
                } else {
                    mostrarToast('Falha ao atualizar personagem.', 'erro');
                }
            } catch (e) { mostrarToast('Erro de rede.', 'erro'); }
        }

        function abrirModalEditarBuild(jogadorId, nome, classe, s4, s5, s6, s7, c3, c4, trin, mt) {
            document.getElementById('editBuildId').value = jogadorId;
            document.getElementById('tituloEditarBuild').innerText = 'Atualizar Build: ' + nome;
            document.getElementById('editBuildClasse').value = classe;
            document.getElementById('editBuildS4').checked = s4;
            document.getElementById('editBuildS5').checked = s5;
            document.getElementById('editBuildS6').checked = s6;
            document.getElementById('editBuildS7').checked = s7;
            document.getElementById('editBuildC3').checked = c3;
            document.getElementById('editBuildC4').checked = c4;
            document.getElementById('editBuildTrin').checked = trin;
            document.getElementById('editBuildMT').checked = mt;
            abrirModal('modalEditarBuild');
        }

        async function salvarEdicaoBuild() {
            const jogadorId = document.getElementById('editBuildId').value;
            const payload = {
                id: jogadorId,
                classe: document.getElementById('editBuildClasse').value,
                skill_4: document.getElementById('editBuildS4').checked,
                skill_5: document.getElementById('editBuildS5').checked,
                skill_6: document.getElementById('editBuildS6').checked,
                skill_7: document.getElementById('editBuildS7').checked,
                constante_3: document.getElementById('editBuildC3').checked,
                constante_4: document.getElementById('editBuildC4').checked,
                trindade: document.getElementById('editBuildTrin').checked,
                mestre_tecnica: document.getElementById('editBuildMT').checked
            };

            try {
                const response = await fetch('/api/editar-jogadores', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ jogadores: [payload] })
                });
                if (response.ok) {
                    fecharModal('modalEditarBuild');
                    await atualizarDados();
                    mostrarToast('Build atualizada com sucesso!', 'sucesso');
                } else {
                    mostrarToast('Falha ao atualizar build.', 'erro');
                }
            } catch (e) { mostrarToast('Erro de rede.', 'erro'); }
        }

        function abrirModalAposta(itemId, nomeItem, maxPontos) {
            document.getElementById('apostaItemId').value = itemId;
            document.getElementById('labelItemAposta').innerText = nomeItem;
            document.getElementById('labelMaxPontos').innerText = `O custo para ter 100% de chance é de ${maxPontos} pts. (Mínimo de 90% de participação semanal exigido).`;
            document.getElementById('apostaPontos').value = '';

            // Reseta a seleção para forçar o usuário a clicar em um nome
            document.getElementById('apostaJogadorId').selectedIndex = 0;
            abrirModal('modalAposta');
        }

        async function confirmarAposta() {
            const selectElement = document.getElementById('apostaJogadorId');
            const jogadorId = selectElement.value;
            const pontos = document.getElementById('apostaPontos').value;
            const itemId = document.getElementById('apostaItemId').value;

            // Bloqueia se o cara tentar apostar sem escolher o nome
            if (!jogadorId) {
                return mostrarToast("Por favor, selecione o SEU PERSONAGEM na lista antes de apostar!", 'aviso');
            }

            if (pontos <= 0 || pontos === "") {
                return mostrarToast("Insira uma pontuação válida para apostar.", 'aviso');
            }

            // Pega o nome do cara selecionado, cortando fora a " (%)" para a confirmação
            const nomeJogadorText = selectElement.options[selectElement.selectedIndex].text;
            const nomeJogador = nomeJogadorText.split(' (')[0];

            // Alerta de confirmação extra de segurança
            const confirmacao = confirm(`Você realmente é o jogador "${nomeJogador}"?\n\nConfirma sua aposta de ${pontos} pontos neste item?`);
            if (!confirmacao) {
                return;
            }

            const payload = {
                item_id: itemId,
                jogador_id: jogadorId,
                pontos: pontos
            };

            const response = await fetch('/api/apostar-item', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            });
            const data = await response.json();
            if(response.ok) { fecharModal('modalAposta'); await atualizarDados(); mostrarToast('Aposta registrada com sucesso!', 'sucesso'); } else { mostrarToast(data.erro, 'erro'); }
        }

        async function removerAposta(apostaId) {
            if(!confirm("Remover aposta?")) return;
            await fetch(`/api/remover-aposta/${apostaId}`, {method: 'DELETE'});
            await atualizarDados();
            mostrarToast('Aposta removida.', 'info');
        }

        /* --- LÓGICA DA ROLETA CANVAS MULTIPLAYER E RESPONSIVA --- */
        let dadosSorteioAtual = null;
        let roletaIsSpinning = false;

        async function pollSorteioAoVivo() {
            if (roletaIsSpinning) return;
            try {
                let res = await fetch('/api/status-sorteio-ao-vivo');
                if (res.ok) {
                    let data = await res.json();
                    if (data.ativo && !roletaIsSpinning) {
                        dadosSorteioAtual = data.dados;
                        iniciarAnimacaoRoletaCanvas(dadosSorteioAtual.fatias, dadosSorteioAtual.vencedor_nome, dadosSorteioAtual.nome_item);
                    }
                }
            } catch(e) {}
        }

            setInterval(pollSorteioAoVivo, 2500);

        const DELAY_SUSPENSE_ROLETA_MS = 1200;

        function abrirModalStaffRoleta(itemId, nomeItem) {
            document.getElementById('staffRoletaItemId').value = itemId;
            document.getElementById('staffRoletaNomeItem').value = nomeItem;
            document.getElementById('novoStaffNome').value = '';

            // Mostra quem já apostou neste item, lendo direto do card já renderizado na tela
            const card = document.querySelector(`.item-card[data-item-id="${itemId}"]`);
            const listaPresentes = document.getElementById('listaJogadoresPresentes');
            listaPresentes.innerHTML = '';
            const apostas = card ? card.querySelectorAll('.lista-apostas-item > span') : [];
            if (apostas.length === 0) {
                listaPresentes.innerHTML = '<span>Nenhum jogador apostou neste item ainda.</span>';
            } else {
                apostas.forEach(span => {
                    const nomeTexto = (span.childNodes[0] ? span.childNodes[0].textContent : span.textContent).trim();
                    const tag = document.createElement('span');
                    tag.style.cssText = 'background: rgba(0,243,255,0.1); border: 1px solid var(--glass-border); padding: 4px 8px; border-radius: 4px; color: #fff;';
                    tag.innerText = nomeTexto;
                    listaPresentes.appendChild(tag);
                });
            }

            abrirModal('modalStaffRoleta');
        }

        async function adicionarStaff() {
            const input = document.getElementById('novoStaffNome');
            const nome = input.value.trim();
            if (!nome) { mostrarToast('Digite um nome antes de adicionar.', 'aviso'); return; }

            try {
                const response = await fetch('/api/criar-staff', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ nome: nome })
                });
                const data = await response.json();
                if (response.ok) {
                    input.value = '';
                    await atualizarElementoParcial('listaStaffGerenciamento');
                    mostrarToast('Pessoa adicionada à Staff!', 'sucesso');
                } else {
                    mostrarToast(data.erro, 'erro');
                }
            } catch (e) { mostrarToast('Erro de rede.', 'erro'); }
        }

        async function removerStaff(id) {
            if (!confirm('Remover esta pessoa da lista de Staff?')) return;
            try {
                const response = await fetch(`/api/deletar-staff/${id}`, { method: 'DELETE' });
                if (response.ok) {
                    await atualizarElementoParcial('listaStaffGerenciamento');
                    mostrarToast('Removido da Staff.', 'info');
                } else {
                    const data = await response.json();
                    mostrarToast(data.erro, 'erro');
                }
            } catch (e) { mostrarToast('Erro de rede.', 'erro'); }
        }

        async function salvarNomesStaff() {
            const linhas = document.querySelectorAll('#listaStaffGerenciamento .linha-staff-gerenciamento');
            const staffData = Array.from(linhas).map(linha => ({
                id: linha.getAttribute('data-staff-id'),
                nome: linha.querySelector('.staff-nome-input').value
            }));
            if (staffData.length === 0) { mostrarToast('Nenhuma pessoa cadastrada para salvar.', 'aviso'); return; }

            try {
                const response = await fetch('/api/editar-staff', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ staff: staffData })
                });
                if (response.ok) {
                    await atualizarElementoParcial('listaStaffGerenciamento');
                    mostrarToast('Nomes da Staff atualizados!', 'sucesso');
                } else {
                    mostrarToast('Falha ao salvar nomes.', 'erro');
                }
            } catch (e) { mostrarToast('Erro de rede.', 'erro'); }
        }

        async function confirmarStaffEGirarRoleta() {
            const itemId = document.getElementById('staffRoletaItemId').value;
            const nomeItem = document.getElementById('staffRoletaNomeItem').value;
            const radioSelecionado = document.querySelector('input[name="staffSelecionado"]:checked');

            if (!radioSelecionado) {
                mostrarToast('Selecione quem da Staff vai representar este sorteio.', 'aviso');
                return;
            }

            fecharModal('modalStaffRoleta');
            await prepararRoletaItem(itemId, nomeItem, radioSelecionado.value);
        }

        async function prepararRoletaItem(itemId, nomeItem, nomeStaff) {
            try {
                const response = await fetch('/api/simular-sorteio-item', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ item_id: itemId, nome_staff: nomeStaff })
                });
                const data = await response.json();

                if (response.ok) {
                    dadosSorteioAtual = data;
                    // Pequeno suspense antes de abrir a roleta; ela já entra girando (sorteio decidido no servidor)
                    setTimeout(() => {
                        iniciarAnimacaoRoletaCanvas(data.fatias, data.vencedor_nome, nomeItem);
                    }, DELAY_SUSPENSE_ROLETA_MS);
                } else {
                    mostrarToast(data.erro, 'erro');
                }
            } catch(e) { mostrarToast("Erro de rede.", 'erro'); }
        }

        function iniciarAnimacaoRoletaCanvas(fatias, vencedorNome, nomeItem) {
            roletaIsSpinning = true;
            document.getElementById('tituloRoletaVisual').innerText = "SORTEANDO: " + nomeItem.toUpperCase();
            abrirModal('modalRoletaItem');

            const wrapper = document.getElementById('wrapperCanvas');
            const canvas = document.getElementById('canvasRoleta');
            const ctx = canvas.getContext('2d');
            const labelVencedor = document.getElementById('roletaVencedorLabel');
            const btnFechar = document.getElementById('btnFecharRoletaVisual');

            wrapper.style.transition = 'none';
            wrapper.style.transform = 'rotate(0deg)';
            labelVencedor.style.display = 'none';
            btnFechar.style.display = 'none';

            if (isAdmin()) {
                btnFechar.innerText = "Concluir (Pontos Descontados)";
                btnFechar.onclick = async () => {
                    btnFechar.innerText = "Salvando..."; btnFechar.disabled = true;
                    await fetch('/api/confirmar-sorteio-item', {
                        method: 'POST', headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(dadosSorteioAtual)
                    });
                    fecharModal('modalRoletaItem');
                    roletaIsSpinning = false;
                    await atualizarDados();
                    mostrarToast('Sorteio finalizado e pontos descontados!', 'sucesso');
                };
            } else {
                btnFechar.innerText = "Sorteio Finalizado - Fechar";
                btnFechar.onclick = async () => { fecharModal('modalRoletaItem'); roletaIsSpinning = false; await atualizarDados(); };
            }

            const centerX = canvas.width / 2;
            const centerY = canvas.height / 2;
            const radius = Math.min(centerX, centerY) - 2;

            ctx.clearRect(0, 0, canvas.width, canvas.height);

            const cores = ['#3498db', '#e74c3c', '#2ecc71', '#f1c40f', '#9b59b6', '#00f3ff', '#bc13fe', '#ffaa00', '#ff003c', '#10b981'];
            let colorIndex = 0;

            let visualFatias = {};
            let totalVisual = 0;
            for (const [nome, porcentagem] of Object.entries(fatias)) {
                let p = parseFloat(porcentagem);
                if (p <= 0) continue;

                let visualP = Math.max(p, 4.0);
                visualFatias[nome] = { realP: p, visualP: visualP };
                totalVisual += visualP;
            }

            let startAngle = -Math.PI / 2;
            let currentDegAcumulado = 0;
            let startWinDeg = 0;
            let endWinDeg = 0;

            for (const [nome, dataFat] of Object.entries(visualFatias)) {
                let fatiaVisualDeg = (dataFat.visualP / totalVisual) * 360;

                if (nome === vencedorNome) {
                    startWinDeg = currentDegAcumulado;
                    endWinDeg = currentDegAcumulado + fatiaVisualDeg;
                }
                currentDegAcumulado += fatiaVisualDeg;

                const sliceAngle = (dataFat.visualP / totalVisual) * 2 * Math.PI;
                const endAngle = startAngle + sliceAngle;

                ctx.beginPath();
                ctx.moveTo(centerX, centerY);
                ctx.arc(centerX, centerY, radius, startAngle, endAngle);
                ctx.closePath();
                ctx.fillStyle = cores[colorIndex % cores.length];
                ctx.fill();

                ctx.lineWidth = 4;
                ctx.strokeStyle = '#111';
                ctx.stroke();

                ctx.save();
                ctx.translate(centerX, centerY);
                ctx.rotate(startAngle + sliceAngle / 2);
                ctx.textAlign = "right";

                let textNome = nome.length > 15 ? nome.substring(0, 15) + "..." : nome;
                let textoFinal = `${textNome} (${dataFat.realP.toFixed(1)}%)`;

                ctx.fillStyle = "#fff";
                ctx.font = "bold 16px 'Rajdhani'";
                ctx.shadowColor = "rgba(0,0,0,1)"; ctx.shadowBlur = 4; ctx.shadowOffsetX = 2; ctx.shadowOffsetY = 2;

                ctx.lineWidth = 3;
                ctx.strokeStyle = "#000";
                ctx.strokeText(textoFinal, radius - 15, 5);
                ctx.fillText(textoFinal, radius - 15, 5);

                ctx.restore();

                startAngle = endAngle;
                colorIndex++;
            }

            setTimeout(() => {
                const margin = (endWinDeg - startWinDeg) * 0.1;
                const winDeg = startWinDeg + margin + (Math.random() * ((endWinDeg - startWinDeg) - (margin * 2)));

                const rotacaoParaTopo = 360 - winDeg;
                const voltasCompletas = 360 * 12;
                const rotacaoFinal = voltasCompletas + rotacaoParaTopo;

                wrapper.style.transition = 'transform 6s cubic-bezier(0.2, 0, 0, 1)';
                wrapper.style.transform = `rotate(${rotacaoFinal}deg)`;

                setTimeout(() => {
                    labelVencedor.innerText = "🏆 " + vencedorNome + " 🏆";
                    labelVencedor.style.display = 'block';
                    btnFechar.style.display = 'block';
                }, 6200);

            }, 100);
        }


        /* --- LÓGICA DE EDIÇÃO E HISTÓRICO ORIGINAL --- */
        async function salvarEdicoes() {
            const linhasModificadas = document.querySelectorAll('tr.linha-modificada:not(.mega-clone):not(.tita-clone)');
            if (linhasModificadas.length === 0) { mostrarToast("Nenhuma alteração detectada para ser salva.", 'aviso'); return; }
            let jogadoresData = [];
            linhasModificadas.forEach(linha => {
                const inNome = linha.querySelector('.edit-nome');
                const inAlts = linha.querySelector('.edit-alts');
                const inLevel = linha.querySelector('.edit-level');
                const inPoder = linha.querySelector('.edit-poder');
                const inPontos = linha.querySelector('.edit-pontos');
                const inClasse = linha.querySelector('.edit-classe');
                const ckS4 = linha.querySelector('.check-s4');
                const ckS5 = linha.querySelector('.check-s5');
                const ckS6 = linha.querySelector('.check-s6');
                const ckS7 = linha.querySelector('.check-s7');
                const ckC3 = linha.querySelector('.check-c3');
                const ckC4 = linha.querySelector('.check-c4');
                const ckTrin = linha.querySelector('.check-trin');
                const ckMT = linha.querySelector('.check-mt');

                jogadoresData.push({
                    id: linha.getAttribute('data-jogador-id'),
                    nome: inNome ? inNome.value : null,
                    alts: inAlts ? inAlts.value : null,
                    level: inLevel ? inLevel.value : null,
                    poder_combate: inPoder ? inPoder.value : null,
                    pontos: inPontos ? inPontos.value : null,
                    classe: inClasse ? inClasse.value : null,
                    skill_4: ckS4 ? ckS4.checked : null,
                    skill_5: ckS5 ? ckS5.checked : null,
                    skill_6: ckS6 ? ckS6.checked : null,
                    skill_7: ckS7 ? ckS7.checked : null,
                    constante_3: ckC3 ? ckC3.checked : null,
                    constante_4: ckC4 ? ckC4.checked : null,
                    trindade: ckTrin ? ckTrin.checked : null,
                    mestre_tecnica: ckMT ? ckMT.checked : null,
                    eventos: {}
                });
            });

            try {
                const response = await fetch('/api/editar-jogadores', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ jogadores: jogadoresData })
                });
                if (response.ok) { await atualizarDados(); mostrarToast("Sincronização concluída apenas para as modificações feitas!", 'sucesso'); } else { mostrarToast('Falha ao gravar alterações.', 'erro'); }
            } catch (error) { mostrarToast('Erro de rede.', 'erro'); }
        }

        async function salvarHistorico() {
            let historicoData = [];
            document.querySelectorAll('tr[data-historico-id]').forEach(linha => {
                historicoData.push({ id: linha.getAttribute('data-historico-id'), observacao: linha.querySelector('.hist-obs').value, penalidade: linha.querySelector('.hist-penalidade').value });
            });
            const response = await fetch('/api/editar-historico', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ historico: historicoData }) });
            if (response.ok) { await atualizarDados(); mostrarToast("Registros atualizados.", 'sucesso'); }
        }

        async function deletarHistorico(id) {
            if (!confirm("Aviso: Purgar este registro restaurará os pontos deduzidos do jogador. Confirmar?")) return;
            const response = await fetch(`/api/deletar-historico/${id}`, { method: 'DELETE' });
            if (response.ok) { await atualizarDados(); mostrarToast('Registro purgado.', 'info'); }
        }

        /* --- LÓGICA DE IMPORTAÇÃO E ADMIN (NOVA SEMANA) --- */

        async function avancarSemana() {
            if(!confirm("ATENÇÃO: Isso iniciará uma nova semana no calendário. O cálculo de 90% de presença recomeçará do zero para todos os jogadores. Os pontos já ganhos continuarão guardados no saldo total. Confirma a virada de semana?")) return;

            try {
                const response = await fetch('/api/nova-semana', { method: 'POST' });
                const data = await response.json();
                if(response.ok) { await atualizarDados(); mostrarToast(data.mensagem, 'sucesso'); }
                else { mostrarToast("Erro: " + data.erro, 'erro'); }
            } catch(e) { mostrarToast("Falha na conexão.", 'erro'); }
        }

        async function salvarReguasGlobais() {
            const cpMega = document.getElementById('inputMegaCP').value;
            const cpTita = document.getElementById('inputTitaCP').value;
            try {
                const response = await fetch('/api/salvar-regua', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ cp_mega: cpMega, cp_tita: cpTita })
                });
                const data = await response.json();
                if (response.ok) { await atualizarDados(); mostrarToast(data.mensagem, 'sucesso'); } else { mostrarToast("Erro: " + data.erro, 'erro'); }
            } catch (e) { mostrarToast("Falha de rede.", 'erro'); }
        }

        /* --- GERENCIAMENTO DE MEMBROS (ADMIN) --- */
        async function criarJogador() {
            const nome = document.getElementById('novoJogadorNome').value.trim();
            const level = document.getElementById('novoJogadorLevel').value;
            const poder = document.getElementById('novoJogadorPoder').value;

            if (!nome) { mostrarToast('Informe o nome do membro.', 'aviso'); return; }

            try {
                const response = await fetch('/api/criar-jogador', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ nome: nome, level: level, poder_combate: poder })
                });
                const data = await response.json();
                if (response.ok) {
                    await atualizarDados();
                    mostrarToast(data.mensagem, 'sucesso');
                } else {
                    mostrarToast(data.erro, 'erro');
                }
            } catch (e) { mostrarToast('Erro de rede.', 'erro'); }
        }

        async function deletarJogador(id, nome) {
            if (!confirm(`Remover "${nome}" permanentemente?\n\nTodo o histórico dele será apagado: pontuações, espólios recebidos, sorteios meme e apostas ativas. Esta ação não pode ser desfeita.`)) return;

            try {
                const response = await fetch(`/api/deletar-jogador/${id}`, { method: 'DELETE' });
                const data = await response.json();
                if (response.ok) {
                    await atualizarDados();
                    mostrarToast(data.mensagem, 'info');
                } else {
                    mostrarToast(data.erro, 'erro');
                }
            } catch (e) { mostrarToast('Erro de rede.', 'erro'); }
        }

        async function toggleStatusJogador(id, btnElement) {
            const textoOriginal = btnElement.innerText;
            btnElement.innerText = '...';
            btnElement.disabled = true;

            try {
                const response = await fetch(`/api/toggle-status-jogador/${id}`, { method: 'POST' });
                const data = await response.json();
                if (response.ok) {
                    await atualizarDados();
                    mostrarToast(data.mensagem, 'info');
                } else {
                    mostrarToast(data.erro, 'erro');
                    btnElement.innerText = textoOriginal;
                    btnElement.disabled = false;
                }
            } catch (e) {
                mostrarToast('Erro de rede.', 'erro');
                btnElement.innerText = textoOriginal;
                btnElement.disabled = false;
            }
        }

        async function criarEvento() {
            const payload = { nome: document.getElementById('novoEventoNome').value.trim(), tipo: document.getElementById('novoEventoTipo').value, pontos: document.getElementById('novoEventoPontos').value };
            if(!payload.nome) return mostrarToast("Parâmetro 'Nome' é obrigatório.", 'aviso');
            const response = await fetch('/api/criar-evento', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
            if (response.ok) { document.getElementById('novoEventoNome').value = ''; await atualizarDados(); mostrarToast('Novo evento injetado com sucesso!', 'sucesso'); } else { mostrarToast('Falha ao criar módulo.', 'erro'); }
        }

        async function salvarConfiguracoes() {
            let configsData = [];
            document.querySelectorAll('tr[data-config-id]').forEach(linha => { configsData.push({ id: linha.getAttribute('data-config-id'), pontos: linha.querySelector('.conf-pontos').value }); });
            const response = await fetch('/api/salvar-configuracoes', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ configs: configsData }) });
            if (response.ok) { await atualizarDados(); mostrarToast("Matriz atualizada. Cálculo refeito.", 'sucesso'); }
        }

        async function salvarEdicaoImports() {
            let importsData = [];
            document.querySelectorAll('tr[data-import-id]').forEach(linha => { importsData.push({ id: linha.getAttribute('data-import-id'), nome: linha.querySelector('.imp-nome').value }); });
            const response = await fetch('/api/editar-importacao', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ importacoes: importsData }) });
            if (response.ok) { await atualizarDados(); mostrarToast("Logs gravados.", 'sucesso'); }
        }

        let dadosImportacaoAtual = [];

        async function enviarXML(e) {
            e.preventDefault();
            const btnEnviar = document.getElementById('btnEnviar');
            btnEnviar.innerText = 'Analisando...'; btnEnviar.disabled = true;
            const formData = new FormData(document.getElementById('formImportacao'));
            try {
                const response = await fetch('/api/importar', { method: 'POST', body: formData });
                const data = await response.json();
                if (response.ok) { mostrarPreview(data.preview, data.hash, data.atividades_encontradas); } else { mostrarToast('Falha: ' + data.erro, 'erro'); }
            } catch (error) { mostrarToast('Falha de conexão com o servidor matriz.', 'erro'); } finally { btnEnviar.innerText = 'Processar XML'; btnEnviar.disabled = false; }
        }

        async function enviarExcel(e) {
            e.preventDefault();
            const btnEnviarEx = document.getElementById('btnEnviarExcel');
            btnEnviarEx.innerText = 'Extraindo...'; btnEnviarEx.disabled = true;
            const formData = new FormData(document.getElementById('formExcel'));
            try {
                const response = await fetch('/api/importar-excel', { method: 'POST', body: formData });
                const data = await response.json();
                if (response.ok) { fecharModal('modalImportacao'); await atualizarDados(); mostrarToast(data.mensagem, 'sucesso'); } else { mostrarToast('Falha: ' + data.erro, 'erro'); }
            } catch (error) { mostrarToast('Falha de conexão.', 'erro'); } finally { btnEnviarEx.innerText = 'Sincronizar Atributos'; btnEnviarEx.disabled = false; }
        }

        function mostrarPreview(jogadores, hash, todas_atividades) {
            document.getElementById('formImportacao').parentElement.style.display = 'none';
            document.getElementById('formExcel').parentElement.style.display = 'none';
            document.getElementById('areaPreview').style.display = 'block';
            document.getElementById('hashArquivo').value = hash;
            dadosImportacaoAtual = jogadores;
            const containerEventos = document.getElementById('listaEventosEncontrados');
            containerEventos.innerHTML = '';
            const eventosDiariosPadrao = ['Verificado', 'Doar', 'Atividade da Guilda'];

            if (todas_atividades && todas_atividades.length > 0) {
                todas_atividades.forEach(atv => {
                    const isChecked = eventosDiariosPadrao.includes(atv) ? 'checked' : '';
                    const borderColor = isChecked ? 'var(--neon-cyan)' : 'var(--text-muted)';
                    containerEventos.innerHTML += `<label style="display: flex; align-items: center; gap: 8px; font-size: 15px; color: #fff; cursor: pointer; background: rgba(0,0,0,0.6); padding: 10px 15px; border-radius: 4px; border: 1px solid ${borderColor}; transition: 0.2s;"><input type="checkbox" class="check-evento-import" value="${atv}" ${isChecked} onchange="atualizarPreviewPontos(this)" style="accent-color: var(--neon-cyan); width: 18px; height: 18px;">${atv}</label>`;
                });
            } else { containerEventos.innerHTML = '<span style="color: var(--text-muted); font-size: 14px;">Nenhum evento detectado.</span>'; }
            atualizarPreviewPontos();
        }

        function atualizarPreviewPontos(checkboxElement = null) {
            if (checkboxElement) {
                const label = checkboxElement.parentElement;
                label.style.borderColor = checkboxElement.checked ? 'var(--neon-cyan)' : 'var(--text-muted)';
            }
            const checkboxes = document.querySelectorAll('.check-evento-import:checked');
            const eventosMarcados = Array.from(checkboxes).map(cb => cb.value);
            const isBlackSkull = document.getElementById('guildaAlvoSelect').value === 'blackskull';
            const eventosPermitidosBS = ['Raid de Guilda', 'Expedição da Guilda'];
            let html = '<ul style="list-style: none; padding: 0; margin: 0;">';
            let temDesconhecido = false;

            dadosImportacaoAtual.forEach(j => {
                let cor = j.encontrado_no_bd ? '#10b981' : '#ff003c';
                if (!j.encontrado_no_bd) temDesconhecido = true;
                let labelStatus = j.encontrado_no_bd ? '[OK]' : '[NÃO VINCULADO]';
                let pontosCalculados = 0;
                j.detalhes.forEach(det => {
                    if (eventosMarcados.includes(det.atividade)) {
                        if (!isBlackSkull || eventosPermitidosBS.includes(det.atividade)) pontosCalculados += det.pontos;
                    }
                });
                html += `<li style="display: flex; justify-content: space-between; border-bottom: 1px dashed rgba(255,255,255,0.1); padding: 8px 0;"><span style="color: ${cor}">${labelStatus} ${j.nome_xml}</span><span style="color: var(--neon-cyan);">+${pontosCalculados} pts (tentativa)</span></li>`;
            });
            html += '</ul>';
            document.getElementById('resultadoPreview').innerHTML = html;

            if(temDesconhecido && !isBlackSkull) { document.getElementById('areaAlertaNovos').style.display = 'flex'; }
            else {
                document.getElementById('areaAlertaNovos').style.display = 'none';
                if(isBlackSkull && temDesconhecido) document.getElementById('resultadoPreview').innerHTML += '<p style="color: var(--neon-orange); margin-top: 10px; font-size: 13px;">⚠️ Alts "NÃO VINCULADOS" serão ignorados na injeção.</p>';
            }
        }

        async function confirmarImportacao(e) {
            e.preventDefault();
            const btnConfirmar = e.target.querySelector('button[type="submit"]');
            btnConfirmar.innerText = 'Injetando no DB...'; btnConfirmar.disabled = true;
            const checkboxesEventos = document.querySelectorAll('.check-evento-import:checked');
            const eventosSelecionados = Array.from(checkboxesEventos).map(cb => cb.value);

            const payload = {
                hash: document.getElementById('hashArquivo').value,
                jogadores: dadosImportacaoAtual,
                guilda_alvo: document.getElementById('guildaAlvoSelect').value,
                cadastrar_novos: document.getElementById('checkCadastrarNovos') ? document.getElementById('checkCadastrarNovos').checked : false,
                eventos_selecionados: eventosSelecionados
            };

            try {
                const response = await fetch('/api/confirmar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
                const data = await response.json();
                if (response.ok) { fecharModal('modalImportacao'); await atualizarDados(); mostrarToast('Operação bem sucedida: ' + data.mensagem, 'sucesso'); } else { mostrarToast('Falha na operação: ' + data.erro, 'erro'); btnConfirmar.innerText = 'Confirmar Injeção de Dados'; btnConfirmar.disabled = false; }
            } catch (error) { mostrarToast('Falha no servidor.', 'erro'); btnConfirmar.disabled = false; }
        }

        async function deletarImportacao(id) {
            if (!confirm("Aviso Crítico: Purgar este upload irá DESFAZER TODOS OS PONTOS adicionados por ele. Confirma?")) return;
            const response = await fetch(`/api/deletar-importacao/${id}`, { method: 'DELETE' });
            if (response.ok) { await atualizarDados(); mostrarToast('Rollback concluído! Importação e pontos desfeitos.', 'info'); }
        }

        /* --- LÓGICA DO SORTEIO MEME --- */
        function toggleTodosMeme(source) { document.querySelectorAll('.check-meme').forEach(cb => cb.checked = source.checked); }

        async function abrirRoletaMeme() {
            const checkboxes = document.querySelectorAll('.check-meme:checked');
            const itemInput = document.getElementById('inputItemMeme').value.trim();
            if (!itemInput) { mostrarToast('Parâmetro ausente: Por favor, digite o nome do item a ser sorteado.', 'aviso'); return; }
            if (checkboxes.length === 0) { mostrarToast('Parâmetros insuficientes: Selecione alvos para o sorteio meme.', 'aviso'); return; }

            const idsSet = new Set();
            const nomesMap = new Map();
            checkboxes.forEach(cb => { idsSet.add(cb.value); nomesMap.set(cb.value, cb.dataset.nome); });
            const idsSelecionados = Array.from(idsSet);
            const nomesSelecionados = idsSelecionados.map(id => nomesMap.get(id));

            const roletaNomeMeme = document.getElementById('roletaNomeMeme');
            const btnFecharRoletaMeme = document.getElementById('btnFecharRoletaMeme');
            document.getElementById('tituloRoletaMeme').innerText = `Sorteando (Meme): ${itemInput.toUpperCase()}`;
            roletaNomeMeme.style.color = "white"; btnFecharRoletaMeme.style.display = 'none';
            abrirModal('modalRoletaMeme');

            let i = 0;
            const intervaloAnimacao = setInterval(() => { roletaNomeMeme.innerText = nomesSelecionados[i % nomesSelecionados.length]; i++; }, 50);

            try {
                const response = await fetch('/api/realizar-sorteio-meme', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ jogadores_ids: idsSelecionados, item: itemInput }) });
                const data = await response.json();
                if (response.ok) {
                    setTimeout(() => {
                        clearInterval(intervaloAnimacao);
                        roletaNomeMeme.innerText = "🏆 " + data.vencedor_nome + " 🏆";
                        roletaNomeMeme.style.color = "var(--neon-cyan)";
                        roletaNomeMeme.style.textShadow = "0 0 20px rgba(0,243,255,0.8)";
                        btnFecharRoletaMeme.style.display = 'block';
                    }, 2500);
                } else { clearInterval(intervaloAnimacao); mostrarToast("Falha: " + data.erro, 'erro'); fecharModal('modalRoletaMeme'); }
            } catch (error) { clearInterval(intervaloAnimacao); mostrarToast('Falha de rede.', 'erro'); fecharModal('modalRoletaMeme'); }
        }

        async function salvarHistoricoMeme() {
            let historicoData = [];
            document.querySelectorAll('tr[data-historico-meme-id]').forEach(linha => { historicoData.push({ id: linha.getAttribute('data-historico-meme-id'), observacao: linha.querySelector('.hist-meme-obs').value }); });
            const response = await fetch('/api/editar-historico-meme', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ historico: historicoData }) });
            if (response.ok) { await atualizarDados(); mostrarToast("Registros Meme atualizados.", 'sucesso'); }
        }

        async function deletarHistoricoMeme(id) {
            if (!confirm("Aviso: Purgar este registro de sorteio meme. Confirmar?")) return;
            const response = await fetch(`/api/deletar-historico-meme/${id}`, { method: 'DELETE' });
            if (response.ok) { await atualizarDados(); mostrarToast('Registro purgado.', 'info'); }
        }

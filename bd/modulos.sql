CREATE TABLE IF NOT EXISTS contas (
    usuario_id INTEGER PRIMARY KEY REFERENCES usuarios(id),
    senha_hash TEXT NOT NULL,
    perfil TEXT NOT NULL CHECK (perfil IN ('construtora','mestre_de_obras','cliente')),
    construtora_id INTEGER REFERENCES construtoras(id),
    CHECK ((perfil = 'construtora') = (construtora_id IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS imagens_diario (
    foto_id INTEGER PRIMARY KEY REFERENCES fotos_diario(id),
    tipo TEXT NOT NULL CHECK (tipo IN ('image/jpeg','image/png')),
    conteudo BLOB NOT NULL
);

CREATE TABLE IF NOT EXISTS checklist_diario (
    id INTEGER PRIMARY KEY,
    registro_id INTEGER NOT NULL REFERENCES registros_diario(id),
    descricao TEXT NOT NULL,
    concluido INTEGER NOT NULL DEFAULT 0 CHECK (concluido IN (0,1))
);

CREATE TABLE IF NOT EXISTS acessos_revogados (
    obra_id INTEGER NOT NULL,
    usuario_id INTEGER NOT NULL,
    perfil TEXT NOT NULL,
    PRIMARY KEY (obra_id, usuario_id, perfil),
    FOREIGN KEY (obra_id, usuario_id, perfil)
        REFERENCES participantes_obra(obra_id, usuario_id, perfil)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_etapa_obra ON etapas(id, obra_id);

CREATE TABLE IF NOT EXISTS orcamentos_itens (
    id INTEGER PRIMARY KEY,
    obra_id INTEGER NOT NULL REFERENCES obras(id),
    etapa_id INTEGER,
    descricao TEXT NOT NULL,
    valor_centavos INTEGER NOT NULL CHECK (valor_centavos > 0),
    FOREIGN KEY (etapa_id, obra_id) REFERENCES etapas(id, obra_id)
);

CREATE TABLE IF NOT EXISTS lancamentos (
    id INTEGER PRIMARY KEY,
    obra_id INTEGER NOT NULL REFERENCES obras(id),
    descricao TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('receita','despesa')),
    valor_centavos INTEGER NOT NULL CHECK (valor_centavos > 0),
    vencimento TEXT NOT NULL,
    liquidado INTEGER NOT NULL DEFAULT 0 CHECK (liquidado IN (0,1))
);

CREATE TABLE IF NOT EXISTS alteracoes_obra (
    id INTEGER PRIMARY KEY,
    obra_id INTEGER NOT NULL REFERENCES obras(id),
    titulo TEXT NOT NULL,
    previsto TEXT,
    proposto TEXT,
    justificativa TEXT NOT NULL,
    impacto_centavos INTEGER NOT NULL,
    impacto_dias INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pendente' CHECK (status IN ('pendente','aprovada','ajuste')),
    criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS decisoes_obra (
    id INTEGER PRIMARY KEY,
    alteracao_id INTEGER NOT NULL REFERENCES alteracoes_obra(id),
    autor_id INTEGER REFERENCES usuarios(id),
    acao TEXT NOT NULL CHECK (acao IN ('aprovada','ajuste')),
    motivo TEXT,
    criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_diario_obra ON registros_diario(obra_id, data_registro);
CREATE INDEX IF NOT EXISTS idx_orcamentos_obra ON orcamentos_itens(obra_id);
CREATE INDEX IF NOT EXISTS idx_lancamentos_obra ON lancamentos(obra_id, vencimento);
CREATE INDEX IF NOT EXISTS idx_alteracoes_obra ON alteracoes_obra(obra_id, status);

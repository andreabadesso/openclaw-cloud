-- 007_bundles.sql: Agent Bundles
-- Replaces the static niche system with database-driven bundles

CREATE TABLE bundles (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    icon        TEXT NOT NULL DEFAULT '🤖',
    color       TEXT NOT NULL DEFAULT '#10B981',
    status      TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'archived')),
    prompts     JSONB NOT NULL DEFAULT '{}',
    default_model          TEXT NOT NULL DEFAULT 'kimi-coding/k2p5',
    default_thinking_level TEXT NOT NULL DEFAULT 'medium',
    default_language       TEXT NOT NULL DEFAULT 'en',
    providers   JSONB NOT NULL DEFAULT '[]',
    mcp_servers JSONB NOT NULL DEFAULT '{}',
    skills      JSONB NOT NULL DEFAULT '[]',    -- ["skill-slug-1", "skill-slug-2"]
    sort_order  INT NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Add bundle_id FK to boxes
ALTER TABLE boxes ADD COLUMN bundle_id UUID REFERENCES bundles(id);

-- Seed: General bundle
INSERT INTO bundles (slug, name, description, icon, color, status, prompts, default_model, default_thinking_level, default_language, providers, sort_order)
VALUES (
    'general',
    'General Assistant',
    'A versatile AI agent for any use case.',
    '🤖',
    '#10B981',
    'published',
    '{}',
    'kimi-coding/k2p5',
    'medium',
    'en',
    '[]',
    0
);

-- Seed: Pharmacy bundle
INSERT INTO bundles (slug, name, description, icon, color, status, prompts, default_model, default_thinking_level, default_language, providers, sort_order)
VALUES (
    'pharmacy',
    'Pharmacy Assistant',
    'Specialized assistant for pharmacies — drug interactions, inventory, customer service.',
    '💊',
    '#8B5CF6',
    'published',
    '{"soul": "Voce e um assistente farmaceutico especializado. Seu papel e ajudar farmaceuticos e atendentes com consultas de bulas, interacoes medicamentosas, controle de estoque e validade, atendimento ao cliente e integracao com sistemas de gestao. Sempre responda em portugues brasileiro. Seja preciso com informacoes sobre medicamentos e alerte sobre interacoes perigosas ou contraindicacoes."}',
    'kimi-coding/k2p5',
    'medium',
    'pt',
    '[{"provider": "google", "required": false}]',
    1
);

-- Backfill existing boxes: match niche='pharmacy' → pharmacy bundle, else general
UPDATE boxes SET bundle_id = (SELECT id FROM bundles WHERE slug = 'pharmacy') WHERE niche = 'pharmacy';
UPDATE boxes SET bundle_id = (SELECT id FROM bundles WHERE slug = 'general') WHERE bundle_id IS NULL AND status != 'destroyed';

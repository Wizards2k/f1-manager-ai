const BOOTSTRAP_ID = 'ers-manager-bootstrap';

function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
}

function toNumber(value, fallback = 0) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
}

function formatNumber(value, digits = 3) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed.toFixed(digits) : (0).toFixed(digits);
}

function formatMj(value) {
    return formatNumber(value, 2);
}

function percentToRatio(value) {
    return clamp(toNumber(value, 0), 0, 100) / 100;
}

function ratioToPercent(value) {
    return clamp(toNumber(value, 0), 0, 1) * 100;
}

function readBootstrap() {
    const el = document.getElementById(BOOTSTRAP_ID);
    if (!el) {
        return {
            circuit_id: null,
            circuit_name: 'No Active Circuit',
            source_file: null,
            battery_capacity_mj: 4.0,
            deploy_limit_mj: 4.0,
            harvest_limit_mj: 2.0,
            regen_profile: {},
            ers_budget: {},
            soc_warnings: [],
            maps: [],
            selected_map_id: null,
            selected_map: null,
            errors: ['ERS bootstrap not found'],
        };
    }

    try {
        const raw = (el.textContent || '').trim();
        const parsed = raw ? JSON.parse(raw) : {};
        return {
            circuit_id: parsed.circuit_id ?? null,
            circuit_name: parsed.circuit_name ?? 'No Active Circuit',
            source_file: parsed.source_file ?? null,
            battery_capacity_mj: toNumber(parsed.battery_capacity_mj, 4.0),
            deploy_limit_mj: toNumber(parsed.deploy_limit_mj, 4.0),
            harvest_limit_mj: toNumber(parsed.harvest_limit_mj, 2.0),
            regen_profile: parsed.regen_profile || {},
            ers_budget: parsed.ers_budget || {},
            soc_warnings: Array.isArray(parsed.soc_warnings) ? parsed.soc_warnings : [],
            maps: Array.isArray(parsed.maps) ? parsed.maps : [],
            selected_map_id: parsed.selected_map_id ?? null,
            selected_map: parsed.selected_map ?? null,
            errors: Array.isArray(parsed.errors) ? parsed.errors : [],
        };
    } catch (error) {
        console.error('[ERS Manager] Failed to parse bootstrap:', error);
        return {
            circuit_id: null,
            circuit_name: 'No Active Circuit',
            source_file: null,
            battery_capacity_mj: 4.0,
            deploy_limit_mj: 4.0,
            harvest_limit_mj: 2.0,
            regen_profile: {},
            ers_budget: {},
            soc_warnings: [],
            maps: [],
            selected_map_id: null,
            selected_map: null,
            errors: ['Invalid ERS bootstrap payload'],
        };
    }
}

class ErsMapManagerV1 {
    constructor() {
        this.bootstrap = readBootstrap();
        this.catalog = this.bootstrap;
        this.selectedMapId = this.bootstrap.selected_map_id || (this.bootstrap.maps[0]?.id ?? null);
        this.currentMap = null;
        this.percentFieldNames = new Set([
            'target_soc_end_lap',
            'mguh_direct_ratio',
            'bucket_primary_es_deploy_pct',
            'bucket_secondary_es_deploy_pct',
            'bucket_exit_es_deploy_pct',
            'bucket_primary_pct',
            'bucket_secondary_pct',
            'bucket_exit_pct',
        ]);
        this.mjFieldNames = new Set([
            'battery_capacity_mj',
            'deploy_limit_mj',
            'harvest_limit_mj',
            'deploy_mj_per_lap',
            'harvest_mj_per_lap',
            'defense_reserve_mj',
        ]);
        this.bucketLockId = null;

        this.listElement = document.getElementById('map-list');
        this.errorBanner = document.getElementById('load-error');
        this.messageBox = document.getElementById('message-box');
        this.circuitPickerForm = document.getElementById('circuit-picker-form');
        this.circuitSelect = document.getElementById('circuit-select');
        this.deleteButton = document.getElementById('delete-btn');
        this.saveButton = document.getElementById('save-btn');
        this.reloadButton = document.getElementById('reload-btn');
        this.createButton = document.getElementById('create-btn');
        this.createMapIdInput = document.getElementById('create-map-id');
        this.createSourceMapSelect = document.getElementById('create-source-map');
        this.mapIdInput = document.getElementById('map-id');

        this.summaryEls = {
            title: document.getElementById('selected-map-title'),
            subtitle: document.getElementById('selected-map-subtitle'),
            idTag: document.getElementById('selected-map-id-tag'),
            builtinTag: document.getElementById('selected-map-builtin-tag'),
            deploy: document.getElementById('summary-deploy'),
            direct: document.getElementById('summary-direct'),
            buckets: document.getElementById('summary-buckets'),
            soc: document.getElementById('summary-soc'),
            defense: document.getElementById('summary-defense'),
            builtinNote: document.getElementById('builtin-note'),
        };

        this.fieldIds = {
            battery_capacity_mj: 'battery-capacity-mj',
            deploy_limit_mj: 'deploy-limit-mj',
            harvest_limit_mj: 'harvest-limit-mj',
            deploy_mj_per_lap: 'deploy-mj',
            harvest_mj_per_lap: 'harvest-mj',
            target_soc_end_lap: 'target-soc-end',
            mguh_direct_ratio: 'mguh-direct-ratio',
            defense_reserve_mj: 'defense-reserve-mj',
            bucket_primary_pct: 'bucket-primary-pct',
            bucket_secondary_pct: 'bucket-secondary-pct',
            bucket_exit_pct: 'bucket-exit-pct',
            bucket_primary_es_deploy_pct: 'bucket-primary-es-deploy-pct',
            bucket_secondary_es_deploy_pct: 'bucket-secondary-es-deploy-pct',
            bucket_exit_es_deploy_pct: 'bucket-exit-es-deploy-pct',
        };

        this.bucketDefaults = {
            bucket_primary_pct: 50,
            bucket_secondary_pct: 35,
            bucket_exit_pct: 15,
        };
    }

    init() {
        this.bindEvents();
        if (this.bootstrap.errors.length > 0 && this.errorBanner) {
            this.errorBanner.textContent = this.bootstrap.errors.join('; ');
            this.errorBanner.hidden = false;
        }

        this.renderMapList();
        this.updateCreateSourceOptions();
        this.applyBudgetRootToForm();

        if (this.selectedMapId) {
            this.selectMap(this.selectedMapId, { silent: true });
        } else if (this.catalog.maps?.length > 0) {
            this.selectMap(this.catalog.maps[0].id, { silent: true });
        } else {
            this.resetFormToDefaults();
        }

        this.updateSummary();
        this.updateActionState();
        this.syncAllPercentDisplays();
    }

    bindEvents() {
        this.bindCircuitPicker();
        this.bindBucketLockControls();

        if (this.listElement) {
            this.listElement.addEventListener('click', (event) => {
                const card = event.target.closest('[data-map-id]');
                if (!card) return;
                this.selectMap(card.dataset.mapId);
            });
        }

        Object.entries(this.fieldIds).forEach(([name, id]) => {
            const el = document.getElementById(id);
            if (!el) return;

            if (this.percentFieldNames.has(name)) {
                this.bindPercentControl(name, el);
                return;
            }

            if (this.mjFieldNames.has(name)) {
                const normalizeMjField = () => {
                    const maxValue = (name === 'deploy_mj_per_lap' || name === 'harvest_mj_per_lap') ? 4.0 : Number.POSITIVE_INFINITY;
                    this.normalizeNumericField(id, 0, 2, 0, maxValue);
                    this.updateSummary();
                };
                el.addEventListener('input', normalizeMjField);
                el.addEventListener('change', normalizeMjField);
                return;
            }

            el.addEventListener('input', () => {
                this.updateSummary();
            });
            el.addEventListener('change', () => {
                this.updateSummary();
            });
        });

        if (this.reloadButton) {
            this.reloadButton.addEventListener('click', () => this.reloadCatalog());
        }
        if (this.saveButton) {
            this.saveButton.addEventListener('click', () => this.saveSelectedMap());
        }
        if (this.deleteButton) {
            this.deleteButton.addEventListener('click', () => this.deleteSelectedMap());
        }
        if (this.createButton) {
            this.createButton.addEventListener('click', () => this.createNewMap());
        }
    }

    bindCircuitPicker() {
        if (!this.circuitSelect || !this.circuitPickerForm) return;

        this.circuitSelect.addEventListener('change', () => {
            if (typeof this.circuitPickerForm.requestSubmit === 'function') {
                this.circuitPickerForm.requestSubmit();
            } else {
                this.circuitPickerForm.submit();
            }
        });
    }

    bindBucketLockControls() {
        document.querySelectorAll('[data-bucket-lock]').forEach((button) => {
            button.addEventListener('click', () => {
                const bucketId = button.dataset.bucketLock || null;
                this.setBucketLock(this.bucketLockId === bucketId ? null : bucketId);
            });
        });
    }

    bindPercentControl(name, input) {
        const control = input.closest('[data-percent-control]');
        const display = document.querySelector(`[data-percent-display="${name}"]`);

        const syncFromInput = () => {
            // If this bucket is locked, prevent changes
            if (this.isBucketField(this.fieldIds[name]) && this.bucketLockId === name) {
                return;
            }
            if (this.isBucketField(this.fieldIds[name])) {
                this.normalizeBuckets(this.fieldIds[name]);
            } else {
                this.normalizePercentField(this.fieldIds[name]);
            }
            this.syncPercentDisplay(name, display);
            this.updateSummary();
        };

        input.addEventListener('input', syncFromInput);
        input.addEventListener('change', syncFromInput);

        if (control) {
            control.querySelectorAll('[data-percent-step]').forEach((button) => {
                button.addEventListener('click', () => {
                    // If this bucket is locked, prevent step changes
                    if (this.isBucketField(this.fieldIds[name]) && this.bucketLockId === name) {
                        return;
                    }
                    const delta = toNumber(button.dataset.percentStep, 5);
                    const nextValue = clamp(toNumber(input.value, 0) + delta, 0, 100);
                    input.value = formatNumber(nextValue, 1);
                    syncFromInput();
                });
            });
        }
    }

    setBucketLock(bucketId) {
        this.bucketLockId = bucketId && this.fieldIds[bucketId] ? bucketId : null;
        this.normalizeBuckets();
        this.syncBucketLockUI();
        this.syncAllPercentDisplays();
        this.updateSummary();
    }

    syncBucketLockUI() {
        const buttons = document.querySelectorAll('[data-bucket-lock]');
        buttons.forEach((button) => {
            const bucketId = button.dataset.bucketLock || '';
            const isActive = this.bucketLockId === bucketId;
            button.classList.toggle('active', isActive);
            button.setAttribute('aria-pressed', isActive ? 'true' : 'false');
            button.textContent = isActive ? 'Unlock' : 'Lock';

            const input = this.getInput(this.fieldIds[bucketId]);
            if (input) {
                input.disabled = isActive;
            }

            if (input) {
                const control = input.closest('[data-percent-control]');
                if (control) {
                    control.querySelectorAll('[data-percent-step]').forEach((stepButton) => {
                        stepButton.disabled = isActive;
                    });
                }
            }
        });
    }

    syncPercentDisplay(name, displayEl = null) {
        const input = this.getInput(this.fieldIds[name]);
        const display = displayEl || document.querySelector(`[data-percent-display="${name}"]`);
        if (!input || !display) return;

        const value = clamp(toNumber(input.value, 0), 0, 100);
        input.style.setProperty('--range-progress', `${value}%`);
        display.textContent = `${formatNumber(value, 1)}%`;
    }

    syncAllPercentDisplays() {
        this.percentFieldNames.forEach((name) => this.syncPercentDisplay(name));
        this.syncMjDisplays();
        this.syncBucketLockUI();
    }

    syncMjDisplays() {
        const displays = document.querySelectorAll('[data-mj-display]');
        displays.forEach((display) => {
            const fieldName = display.dataset.mjDisplay;
            if (!fieldName) return;

            const baseFieldName = display.dataset.mjBase || '';
            const sourceFieldId = this.fieldIds[fieldName];
            const sourceInput = this.getInput(sourceFieldId);
            let mjValue = toNumber(sourceInput?.value, 0);

            if (baseFieldName) {
                const baseFieldId = this.fieldIds[baseFieldName];
                const baseInput = this.getInput(baseFieldId);
                const baseFallback = toNumber(this.catalog?.[baseFieldName], 0);
                const baseValue = toNumber(baseInput?.value, baseFallback);
                mjValue = percentToRatio(sourceInput?.value) * baseValue;
            }

            const label = display.dataset.mjLabel || '';
            const suffix = display.dataset.mjSuffix ? ` ${display.dataset.mjSuffix}` : '';
            display.textContent = label
                ? `${label} · ${formatMj(mjValue)} MJ${suffix}`
                : `${formatMj(mjValue)} MJ`;
        });
    }

    isBucketField(id) {
        return id === this.fieldIds.bucket_primary_pct
            || id === this.fieldIds.bucket_secondary_pct
            || id === this.fieldIds.bucket_exit_pct;
    }

    getInput(id) {
        return document.getElementById(id);
    }

    getCurrentMap() {
        return this.catalog.maps.find((map) => map.id === this.selectedMapId) || null;
    }

    getSelectedMapData() {
        const map = this.getCurrentMap();
        return map ? {
            map_data: map.map_data || {},
            budget_data: map.budget_data || {},
            summary: map.summary || {},
            is_builtin: Boolean(map.is_builtin),
            label: map.label || map.id,
        } : null;
    }

    resetFormToDefaults() {
        this.selectedMapId = null;
        this.currentMap = null;
        if (this.mapIdInput) {
            this.mapIdInput.value = '';
        }
        this.setField('deploy_mj_per_lap', 4.0);
        this.normalizeNumericField(this.fieldIds.deploy_mj_per_lap, 4.0, 2, 0, 4.0);
        this.setField('harvest_mj_per_lap', 1.0);
        this.normalizeNumericField(this.fieldIds.harvest_mj_per_lap, 1.0, 2, 0, 4.0);
        this.setField('target_soc_end_lap', 55.0);
        this.setField('mguh_direct_ratio', 45.0);
        this.setField('bucket_primary_es_deploy_pct', 0.0);
        this.setField('bucket_secondary_es_deploy_pct', 0.0);
        this.setField('bucket_exit_es_deploy_pct', 0.0);
        this.setField('defense_reserve_mj', 0.2);
        this.setField('bucket_primary_pct', 50.0);
        this.setField('bucket_secondary_pct', 35.0);
        this.setField('bucket_exit_pct', 15.0);
        this.applyBudgetRootToForm();
        this.setSelectedMapMeta(null);
        this.bucketLockId = null;
        this.syncBucketLockUI();
        this.updateSummary();
        this.updateActionState();
        this.syncAllPercentDisplays();
    }

    applyBudgetRootToForm() {
        this.setField('battery_capacity_mj', this.catalog.battery_capacity_mj ?? 4.0);
        this.setField('deploy_limit_mj', this.catalog.deploy_limit_mj ?? 4.0);
        this.setField('harvest_limit_mj', this.catalog.harvest_limit_mj ?? 2.0);
    }

    setField(name, value) {
        const el = this.getInput(this.fieldIds[name]);
        if (!el) return;
        el.value = typeof value === 'number' ? String(value) : value;
    }

    getField(name, fallback = 0) {
        const el = this.getInput(this.fieldIds[name]);
        if (!el) return fallback;
        if (el.tagName === 'SELECT') {
            return el.value;
        }
        return toNumber(el.value, fallback);
    }

    normalizeBuckets(changedId = null) {
        const ids = [
            this.fieldIds.bucket_primary_pct,
            this.fieldIds.bucket_secondary_pct,
            this.fieldIds.bucket_exit_pct,
        ];

        const values = ids.map((id) => toNumber(this.getInput(id)?.value, 0));
        const changedIndex = changedId ? ids.indexOf(changedId) : -1;
        const lockedFieldId = this.bucketLockId ? this.fieldIds[this.bucketLockId] : null;
        const lockedIndex = lockedFieldId ? ids.indexOf(lockedFieldId) : -1;

        if (lockedIndex >= 0) {
            const lockedId = ids[lockedIndex];
            const lockedInput = this.getInput(lockedId);
            const lockedValue = clamp(toNumber(lockedInput?.value, this.bucketDefaults[this.bucketKeyFromId(lockedId)] || 0), 0, 100);
            if (lockedInput) {
                lockedInput.value = formatNumber(lockedValue, 1);
            }

            const unlockedIds = ids.filter((id) => id !== lockedId);
            const remaining = Math.max(0, 100 - lockedValue);

            if (changedIndex >= 0 && ids[changedIndex] !== lockedId) {
                const changedInput = this.getInput(ids[changedIndex]);
                const changedValue = clamp(toNumber(changedInput?.value, 0), 0, remaining);
                if (changedInput) {
                    changedInput.value = formatNumber(changedValue, 1);
                }
                const otherId = unlockedIds.find((id) => id !== ids[changedIndex]);
                const otherInput = otherId ? this.getInput(otherId) : null;
                if (otherInput) {
                    otherInput.value = formatNumber(Math.max(remaining - changedValue, 0), 1);
                }
            } else {
                const unlockedState = unlockedIds.map((id) => ({ id, value: Math.max(toNumber(this.getInput(id)?.value, 0), 0) }));
                const total = unlockedState.reduce((sum, item) => sum + item.value, 0);
                if (total <= 0) {
                    const defaults = unlockedState.map((item) => this.bucketDefaults[this.bucketKeyFromId(item.id)] || 0);
                    const defaultTotal = defaults.reduce((sum, value) => sum + value, 0) || 1;
                    unlockedState.forEach((item, index) => {
                        const next = remaining * (defaults[index] / defaultTotal);
                        const input = this.getInput(item.id);
                        if (input) input.value = formatNumber(next, 1);
                    });
                } else {
                    unlockedState.forEach((item) => {
                        const next = remaining * (item.value / total);
                        const input = this.getInput(item.id);
                        if (input) input.value = formatNumber(next, 1);
                    });
                }
            }

            return;
        }

        if (changedIndex >= 0) {
            const changedValue = clamp(values[changedIndex], 0, 100);
            const others = ids
                .map((id, index) => ({ id, index, value: index === changedIndex ? 0 : Math.max(values[index], 0) }))
                .filter((item) => item.index !== changedIndex);
            const remaining = Math.max(0, 100 - changedValue);
            const otherTotal = others.reduce((sum, item) => sum + item.value, 0);

            this.getInput(ids[changedIndex]).value = formatNumber(changedValue, 1);

            if (otherTotal <= 0) {
                const defaults = others.map((item) => this.bucketDefaults[this.bucketKeyFromId(item.id)] || 0);
                const defaultTotal = defaults.reduce((sum, value) => sum + value, 0) || 1;
                others.forEach((item, idx) => {
                    const next = remaining * (defaults[idx] / defaultTotal);
                    this.getInput(item.id).value = formatNumber(next, 1);
                });
            } else {
                others.forEach((item) => {
                    const next = remaining * (item.value / otherTotal);
                    this.getInput(item.id).value = formatNumber(next, 1);
                });
            }
        } else {
            const total = values.reduce((sum, value) => sum + value, 0);
            if (total <= 0) {
                ids.forEach((id) => {
                    this.getInput(id).value = formatNumber(this.bucketDefaults[this.bucketKeyFromId(id)], 1);
                });
            } else if (Math.abs(total - 100) > 0.05) {
                ids.forEach((id, index) => {
                    const next = (values[index] / total) * 100;
                    this.getInput(id).value = formatNumber(next, 1);
                });
            }
        }
    }

    bucketKeyFromId(id) {
        switch (id) {
            case this.fieldIds.bucket_primary_pct:
                return 'bucket_primary_pct';
            case this.fieldIds.bucket_secondary_pct:
                return 'bucket_secondary_pct';
            default:
                return 'bucket_exit_pct';
        }
    }

    normalizePercentField(id, min = 0, max = 100) {
        const el = this.getInput(id);
        if (!el) return;
        const value = clamp(toNumber(el.value, min), min, max);
        el.value = formatNumber(value, 1);
    }

    normalizeNumericField(id, fallback = 0, digits = 3, min = Number.NEGATIVE_INFINITY, max = Number.POSITIVE_INFINITY) {
        const el = this.getInput(id);
        if (!el) return;
        const value = clamp(toNumber(el.value, fallback), min, max);
        el.value = formatNumber(value, digits);
    }

    updateSummary() {
        const batteryCapacity = toNumber(this.getInput(this.fieldIds.battery_capacity_mj)?.value, this.catalog.battery_capacity_mj ?? 4.0);
        const deployMj = toNumber(this.getInput(this.fieldIds.deploy_mj_per_lap)?.value, 4.0);
        const targetSoc = toNumber(this.getInput(this.fieldIds.target_soc_end_lap)?.value, 55.0);
        const directRatio = toNumber(this.getInput(this.fieldIds.mguh_direct_ratio)?.value, 45.0);
        const defenseReserve = toNumber(this.getInput(this.fieldIds.defense_reserve_mj)?.value, 0.2);
        const bucketPrimary = toNumber(this.getInput(this.fieldIds.bucket_primary_pct)?.value, 50.0);
        const bucketSecondary = toNumber(this.getInput(this.fieldIds.bucket_secondary_pct)?.value, 35.0);
        const bucketExit = toNumber(this.getInput(this.fieldIds.bucket_exit_pct)?.value, 15.0);

        const deployPctBattery = batteryCapacity > 0 ? (deployMj / batteryCapacity) * 100 : 0;
        const esRatio = Math.max(0, 100 - directRatio);
        const bucketSum = bucketPrimary + bucketSecondary + bucketExit;

        this.syncAllPercentDisplays();

        if (this.summaryEls.deploy) this.summaryEls.deploy.textContent = `${deployPctBattery.toFixed(1)}%`;
        if (this.summaryEls.direct) this.summaryEls.direct.textContent = `${directRatio.toFixed(1)}% / ${esRatio.toFixed(1)}%`;
        if (this.summaryEls.buckets) this.summaryEls.buckets.textContent = `${bucketSum.toFixed(1)}%`;
        if (this.summaryEls.soc) this.summaryEls.soc.textContent = `${targetSoc.toFixed(1)}%`;
        if (this.summaryEls.defense) this.summaryEls.defense.textContent = `${formatMj(defenseReserve)} MJ`;
        this.refreshSelectedMapSubtitle();
    }

    refreshSelectedMapSubtitle() {
        if (!this.summaryEls.subtitle) return;
        if (!this.currentMap) return;

        const batteryCapacity = toNumber(this.getInput(this.fieldIds.battery_capacity_mj)?.value, this.catalog.battery_capacity_mj ?? 4.0);
        const deployLimit = toNumber(this.getInput(this.fieldIds.deploy_limit_mj)?.value, this.catalog.deploy_limit_mj ?? 4.0);
        const harvestLimit = toNumber(this.getInput(this.fieldIds.harvest_limit_mj)?.value, this.catalog.harvest_limit_mj ?? 2.0);
        this.summaryEls.subtitle.textContent = `${this.currentMap.is_builtin ? 'Built-in map' : 'Custom map'} · ${formatMj(this.currentMap.summary?.deploy_mj_per_lap ?? 0)} MJ deploy · ${formatNumber((this.currentMap.summary?.bucket_sum_pct ?? 1) * 100, 1)}% bucket sum · Battery ${formatMj(batteryCapacity)} MJ · Caps ${formatMj(deployLimit)} / ${formatMj(harvestLimit)} MJ`;
    }

    setSelectedMapMeta(map) {
        this.currentMap = map;
        if (this.summaryEls.title) this.summaryEls.title.textContent = map ? map.label : 'No map selected';
        if (this.summaryEls.subtitle) {
            if (map) {
                this.refreshSelectedMapSubtitle();
            } else {
                this.summaryEls.subtitle.textContent = 'Pick a map from the catalog to begin editing.';
            }
        }
        if (this.summaryEls.idTag) this.summaryEls.idTag.textContent = map ? map.id : '—';
        if (this.summaryEls.builtinTag) this.summaryEls.builtinTag.textContent = map ? (map.is_builtin ? 'Built-in' : 'Custom') : 'Custom';
        if (this.summaryEls.builtinNote) this.summaryEls.builtinNote.hidden = !(map && map.is_builtin);
        if (this.mapIdInput) this.mapIdInput.value = map ? map.id : '';
        if (this.createSourceMapSelect) {
            this.createSourceMapSelect.value = map ? map.id : '';
            this.createSourceMapSelect.title = map ? (map.label || map.id) : 'Defaults';
        }
        this.selectedMapId = map ? map.id : null;
        this.applyBudgetRootToForm();
        this.updateActionState();
    }

    selectMap(mapId, { silent = false } = {}) {
        const map = this.catalog.maps.find((entry) => entry.id === mapId) || null;
        if (!map) {
            if (!silent) this.showMessage(`ERS map ${mapId} not found`, 'error');
            return;
        }

        this.selectedMapId = map.id;
        this.applyMapToForm(map);
        this.setSelectedMapMeta(map);
        this.renderMapList();
        this.updateCreateSourceOptions();
        this.updateSummary();
        if (!silent) {
            this.showMessage(`Selected ${map.label}`, 'info');
        }
    }

    applyMapToForm(map) {
        const mapData = map.map_data || {};
        const budgetData = map.budget_data || {};

        if (this.mapIdInput) this.mapIdInput.value = map.id;
        this.setField('deploy_mj_per_lap', budgetData.deploy_mj_per_lap ?? mapData.deploy_mj_per_lap ?? 4.0);
        this.normalizeNumericField(this.fieldIds.deploy_mj_per_lap, 4.0, 2, 0, 4.0);
        this.setField('harvest_mj_per_lap', budgetData.harvest_mj_per_lap ?? mapData.harvest_mj_per_lap ?? 1.0);
        this.normalizeNumericField(this.fieldIds.harvest_mj_per_lap, 1.0, 2, 0, 4.0);
        this.setField('target_soc_end_lap', ratioToPercent(budgetData.target_soc_end_lap ?? mapData.target_soc_end_lap ?? 0.55));
        this.setField('mguh_direct_ratio', ratioToPercent(budgetData.mguh_direct_ratio ?? mapData.mguh_direct_ratio ?? 0.45));
        this.setField('bucket_primary_es_deploy_pct', ratioToPercent(mapData.bucket_primary_es_deploy_pct ?? 0.0));
        this.setField('bucket_secondary_es_deploy_pct', ratioToPercent(mapData.bucket_secondary_es_deploy_pct ?? 0.0));
        this.setField('bucket_exit_es_deploy_pct', ratioToPercent(mapData.bucket_exit_es_deploy_pct ?? 0.0));
        this.setField('defense_reserve_mj', mapData.defense_reserve_mj ?? 0.2);
        this.setField('bucket_primary_pct', ratioToPercent(mapData.bucket_primary_pct ?? 0.5));
        this.setField('bucket_secondary_pct', ratioToPercent(mapData.bucket_secondary_pct ?? 0.35));
        this.setField('bucket_exit_pct', ratioToPercent(mapData.bucket_exit_pct ?? 0.15));
        this.bucketLockId = null;
        this.normalizeBuckets();
        this.syncAllPercentDisplays();
    }

    renderMapList() {
        if (!this.listElement) return;
        const maps = Array.isArray(this.catalog.maps) ? this.catalog.maps : [];
        if (maps.length === 0) {
            this.listElement.innerHTML = '<div class="empty-state">No ERS maps available for this circuit.</div>';
            return;
        }

        this.listElement.innerHTML = maps.map((map) => this.renderMapCard(map)).join('');
        this.listElement.querySelectorAll('[data-map-id]').forEach((button) => {
            button.classList.toggle('active', button.dataset.mapId === this.selectedMapId);
        });
    }

    renderMapCard(map) {
        const summary = map.summary || {};
        const directRatio = toNumber(summary.mguh_direct_ratio, 0.45) * 100;
        const esRatio = toNumber(summary.mguh_es_ratio, 0.55) * 100;
        return `
            <button type="button" class="map-card ${map.id === this.selectedMapId ? 'active' : ''}" data-map-id="${map.id}">
                <div class="title-row">
                    <div class="name">${map.label || map.id}</div>
                    <div class="badge">ERS · ${map.is_builtin ? 'Built-in' : 'Custom'}</div>
                </div>
                <div class="summary">
                    <div><strong>Deploy</strong> ${formatMj(summary.deploy_mj_per_lap ?? 0)} MJ · ${formatNumber(summary.deploy_pct_of_battery ?? 0, 1)}% battery</div>
                    <div><strong>Target SOC</strong> ${formatNumber(summary.target_soc_end_lap ?? 0, 3)}</div>
                    <div><strong>Direct / ES</strong> ${directRatio.toFixed(1)}% / ${esRatio.toFixed(1)}%</div>
                    <div><strong>Bucket Sum</strong> ${formatNumber((summary.bucket_sum_pct ?? 1) * 100, 1)}%</div>
                </div>
            </button>
        `;
    }

    updateCreateSourceOptions() {
        if (!this.createSourceMapSelect) return;
        const options = ['<option value="">Defaults</option>'].concat(
            (this.catalog.maps || []).map((map) => `<option value="${map.id}" ${map.id === this.selectedMapId ? 'selected' : ''}>${map.label || map.id}</option>`)
        );
        this.createSourceMapSelect.innerHTML = options.join('');
        if (this.selectedMapId) {
            this.createSourceMapSelect.value = this.selectedMapId;
        }
        const selectedMap = (this.catalog.maps || []).find((map) => map.id === this.createSourceMapSelect.value) || null;
        this.createSourceMapSelect.title = selectedMap ? (selectedMap.label || selectedMap.id) : 'Defaults';
    }

    updateActionState() {
        const map = this.getCurrentMap();
        if (!this.deleteButton) return;
        this.deleteButton.disabled = !map || map.is_builtin;
    }

    showMessage(message, tone = 'info') {
        if (!this.messageBox) return;
        this.messageBox.hidden = false;
        this.messageBox.textContent = message;
        const colors = {
            success: { border: 'rgba(0, 255, 136, 0.45)', bg: 'rgba(0, 255, 136, 0.12)' },
            error: { border: 'rgba(255, 82, 82, 0.55)', bg: 'rgba(255, 82, 82, 0.14)' },
            warning: { border: 'rgba(255, 170, 0, 0.55)', bg: 'rgba(255, 170, 0, 0.14)' },
            info: { border: 'rgba(255, 46, 82, 0.45)', bg: 'rgba(255, 46, 82, 0.10)' },
        };
        const style = colors[tone] || colors.info;
        this.messageBox.style.borderColor = style.border;
        this.messageBox.style.background = style.bg;
        this.messageBox.style.color = '#f3f6ff';
    }

    hideMessage() {
        if (!this.messageBox) return;
        this.messageBox.hidden = true;
        this.messageBox.textContent = '';
    }

    async reloadCatalog() {
        try {
            const url = new URL('/api/engine/ers/catalog', window.location.origin);
            if (this.catalog.circuit_id) {
                url.searchParams.set('circuit_id', this.catalog.circuit_id);
            }
            if (this.selectedMapId) {
                url.searchParams.set('selected_map_id', this.selectedMapId);
            }
            const response = await fetch(url.toString(), { headers: { 'Accept': 'application/json' } });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            this.catalog = await response.json();
            this.selectedMapId = this.catalog.selected_map_id || (this.catalog.maps?.[0]?.id ?? null);
            this.renderMapList();
            this.updateCreateSourceOptions();
            this.applyBudgetRootToForm();
            if (this.selectedMapId) {
                const map = this.catalog.maps.find((entry) => entry.id === this.selectedMapId);
                if (map) {
                    this.applyMapToForm(map);
                    this.setSelectedMapMeta(map);
                }
            } else {
                this.resetFormToDefaults();
            }
            this.updateSummary();
            this.updateActionState();
            this.showMessage('ERS catalog reloaded', 'success');
        } catch (error) {
            console.error('[ERS Manager] Failed to reload catalog:', error);
            this.showMessage(`Reload failed: ${error.message}`, 'error');
        }
    }

    collectFormPayload() {
        const currentMapData = this.currentMap?.map_data || {};
        return {
            map_data: {
                heat_load_kw: currentMapData.heat_load_kw ?? 260.0,
                torque_ramp: currentMapData.torque_ramp ?? 0.6,
                deployment_style: currentMapData.deployment_style || 'balanced',
                cooling_share: currentMapData.cooling_share ?? 0.5,
                ers_output_kw: currentMapData.ers_output_kw ?? 120.0,
                mguh_power_kw: currentMapData.mguh_power_kw ?? 0.0,
                defense_reserve_mj: toNumber(this.getInput(this.fieldIds.defense_reserve_mj)?.value, 0.2),
                bucket_primary_pct: percentToRatio(this.getInput(this.fieldIds.bucket_primary_pct)?.value),
                bucket_secondary_pct: percentToRatio(this.getInput(this.fieldIds.bucket_secondary_pct)?.value),
                bucket_exit_pct: percentToRatio(this.getInput(this.fieldIds.bucket_exit_pct)?.value),
                bucket_primary_es_deploy_pct: percentToRatio(this.getInput(this.fieldIds.bucket_primary_es_deploy_pct)?.value),
                bucket_secondary_es_deploy_pct: percentToRatio(this.getInput(this.fieldIds.bucket_secondary_es_deploy_pct)?.value),
                bucket_exit_es_deploy_pct: percentToRatio(this.getInput(this.fieldIds.bucket_exit_es_deploy_pct)?.value),
            },
            budget_data: {
                deploy_mj_per_lap: toNumber(this.getInput(this.fieldIds.deploy_mj_per_lap)?.value, 4.0),
                harvest_mj_per_lap: toNumber(this.getInput(this.fieldIds.harvest_mj_per_lap)?.value, 1.0),
                target_soc_end_lap: percentToRatio(this.getInput(this.fieldIds.target_soc_end_lap)?.value),
                mguh_direct_ratio: percentToRatio(this.getInput(this.fieldIds.mguh_direct_ratio)?.value),
            },
            budget_root: {
                battery_capacity_mj: toNumber(this.getInput(this.fieldIds.battery_capacity_mj)?.value, 4.0),
                deploy_limit_mj: toNumber(this.getInput(this.fieldIds.deploy_limit_mj)?.value, 4.0),
                harvest_limit_mj: toNumber(this.getInput(this.fieldIds.harvest_limit_mj)?.value, 2.0),
            },
        };
    }

    async saveSelectedMap() {
        const map = this.getCurrentMap();
        if (!map) {
            this.showMessage('Select a map before saving', 'warning');
            return;
        }

        try {
            const payload = {
                circuit_id: this.catalog.circuit_id,
                map_id: map.id,
                ...this.collectFormPayload(),
            };
            const response = await fetch('/api/engine/ers/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
                body: JSON.stringify(payload),
            });
            const data = await response.json();
            if (!response.ok || !data.ok) {
                throw new Error(data.error || data.message || `HTTP ${response.status}`);
            }
            this.catalog = data.catalog;
            this.selectedMapId = data.selected_map_id || map.id;
            this.renderMapList();
            this.updateCreateSourceOptions();
            this.selectMap(this.selectedMapId, { silent: true });
            this.showMessage(data.message || 'ERS map saved', 'success');
        } catch (error) {
            console.error('[ERS Manager] Save failed:', error);
            this.showMessage(`Save failed: ${error.message}`, 'error');
        }
    }

    async createNewMap() {
        const newMapId = (this.createMapIdInput?.value || '').trim();
        if (!newMapId) {
            this.showMessage('Enter a new map ID', 'warning');
            return;
        }

        try {
            const payload = {
                circuit_id: this.catalog.circuit_id,
                map_id: newMapId,
                source_map_id: this.createSourceMapSelect?.value || '',
                ...this.collectFormPayload(),
            };
            const response = await fetch('/api/engine/ers/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
                body: JSON.stringify(payload),
            });
            const data = await response.json();
            if (!response.ok || !data.ok) {
                throw new Error(data.error || data.message || `HTTP ${response.status}`);
            }
            this.catalog = data.catalog;
            this.selectedMapId = data.selected_map_id || newMapId;
            this.renderMapList();
            this.updateCreateSourceOptions();
            const createdMap = this.catalog.maps.find((entry) => entry.id === this.selectedMapId);
            if (createdMap) {
                this.applyMapToForm(createdMap);
                this.setSelectedMapMeta(createdMap);
                this.updateSummary();
            }
            this.showMessage(data.message || 'ERS map created', 'success');
        } catch (error) {
            console.error('[ERS Manager] Create failed:', error);
            this.showMessage(`Create failed: ${error.message}`, 'error');
        }
    }

    async deleteSelectedMap() {
        const map = this.getCurrentMap();
        if (!map) {
            this.showMessage('Select a map before deleting', 'warning');
            return;
        }
        if (map.is_builtin) {
            this.showMessage('Built-in maps cannot be deleted', 'warning');
            return;
        }
        if (!window.confirm(`Delete ERS map ${map.id}? This cannot be undone.`)) {
            return;
        }

        try {
            const response = await fetch('/api/engine/ers/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
                body: JSON.stringify({
                    circuit_id: this.catalog.circuit_id,
                    map_id: map.id,
                }),
            });
            const data = await response.json();
            if (!response.ok || !data.ok) {
                throw new Error(data.error || data.message || `HTTP ${response.status}`);
            }
            this.catalog = data.catalog;
            this.selectedMapId = data.selected_map_id || (this.catalog.maps?.[0]?.id ?? null);
            this.renderMapList();
            this.updateCreateSourceOptions();
            if (this.selectedMapId) {
                const nextMap = this.catalog.maps.find((entry) => entry.id === this.selectedMapId);
                if (nextMap) {
                    this.applyMapToForm(nextMap);
                    this.setSelectedMapMeta(nextMap);
                }
            } else {
                this.resetFormToDefaults();
            }
            this.showMessage(data.message || 'ERS map deleted', 'success');
        } catch (error) {
            console.error('[ERS Manager] Delete failed:', error);
            this.showMessage(`Delete failed: ${error.message}`, 'error');
        }
    }
}

const manager = new ErsMapManagerV1();
manager.init();

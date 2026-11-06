frappe.listview_settings["Fenestration Profile"] = {
	add_fields: [
		"profile_code",
		"profile_name",
		"series",
		"role",
		"kg_per_m",
		"computed_kg_per_m",
		"use_computed_weight",
		"width_mm",
		"depth_mm",
		"area_mm2",
		"perimeter_mm",
		"ix_mm4",
		"iy_mm4",
		"bar_lengths",
		"dxf_file",
		"section_svg",
		"section_warnings",
	],

	onload(listview) {
		init_card_view_state(listview);
		apply_view_mode(listview);
		setTimeout(() => {
			configure_view_switcher(listview);
		}, 0);
	},

	before_render(listview) {
		const lv = listview || window.cur_list;
		if (!lv || lv.doctype !== "Fenestration Profile") return;
		init_card_view_state(lv);
		configure_view_switcher(lv);
	},

	refresh(listview) {
		const lv = listview || window.cur_list;
		if (!lv || lv.doctype !== "Fenestration Profile") return;
		init_card_view_state(lv);
		configure_view_switcher(lv);
		apply_view_mode(lv, true);
	},
};

function init_card_view_state(listview) {
	if (!listview._card_state) {
		listview._card_state = {
			mode: "card",
			series: "ALL",
			role: "ALL",
			search: "",
			profiles: [],
			loading: false,
		};
	}
}

function configure_view_switcher(listview) {
	const vl = listview.views_list;
	if (!vl) return;

	if (!vl._card_view_patched) {
		vl._card_view_patched = true;

		vl.icon_map = Object.assign({}, vl.icon_map, {
			Card: "layout-dashboard",
		});
		vl.label_map = Object.assign({}, vl.label_map, {
			Card: __("Card View"),
		});

		const origGetViewOptions = vl.get_view_options.bind(vl);
		vl.get_view_options = function () {
			const isCard = listview._card_state?.mode === "card";
			this.current_view = isCard ? "Card" : "List";
			const stdOptions = origGetViewOptions();

			for (const opt of stdOptions) {
				if (opt.label === (this.label_map["List"] || __("List View"))) {
					opt.selected = !isCard;
					delete opt.submenu;
					if (isCard) {
						opt.onclick = () => switch_profile_view_mode(listview, "list");
					} else {
						delete opt.onclick;
					}
				} else {
					opt.selected = false;
				}
			}

			const cardOption = {
				label: __("Card View"),
				icon: this.icon_map["Card"] || "layout-dashboard",
				selected: isCard,
			};
			if (!isCard) {
				cardOption.onclick = () => switch_profile_view_mode(listview, "card");
			}

			return [cardOption, ...stdOptions];
		};

		const origGetTriggerLabel = vl.get_trigger_label.bind(vl);
		vl.get_trigger_label = function () {
			if (listview._card_state?.mode === "card") {
				this.current_view = "Card";
				return __("Card View");
			}
			this.current_view = "List";
			return origGetTriggerLabel();
		};
	}

	vl.current_view = listview._card_state?.mode === "card" ? "Card" : "List";
	vl.refresh_trigger();
}

function switch_profile_view_mode(listview, mode) {
	init_card_view_state(listview);
	listview._card_state.mode = mode;
	configure_view_switcher(listview);
	apply_view_mode(listview, true);
}

function apply_view_mode(listview, forceReload = false) {
	init_card_view_state(listview);
	const isCard = listview._card_state.mode === "card";
	const $frappeList = listview.$frappe_list || listview.$result?.closest(".frappe-list");

	if (!listview._$cardContainer) {
		listview._$cardContainer = $(
			`<div class="fen-profile-card-view" style="display:none;padding:18px 20px;"></div>`
		);
		if ($frappeList && $frappeList.length) {
			$frappeList.before(listview._$cardContainer);
		} else if (listview.page?.main) {
			listview.page.main.append(listview._$cardContainer);
		}
	}

	if (isCard) {
		if (listview.page?.page_form) listview.page.page_form.hide();
		if ($frappeList) $frappeList.hide();
		listview._$cardContainer.show();
		load_and_render_cards(listview, forceReload);
	} else {
		listview._$cardContainer.hide();
		if (listview.page?.page_form) listview.page.page_form.show();
		if ($frappeList) $frappeList.show();
		if (listview.$result) listview.$result.show();
		if (listview.$paging_area) listview.$paging_area.show();
		if (typeof listview.set_result_height === "function") {
			listview.set_result_height();
		}
	}
}

function load_and_render_cards(listview, forceReload = false) {
	const state = listview._card_state;
	if (state.loading) return;
	if (!forceReload && state.profiles && state.profiles.length > 0) {
		render_card_grid(listview);
		return;
	}

	state.loading = true;
	frappe.call({
		method: "frappe.client.get_list",
		args: {
			doctype: "Fenestration Profile",
			fields: [
				"name",
				"profile_code",
				"profile_name",
				"series",
				"role",
				"kg_per_m",
				"computed_kg_per_m",
				"use_computed_weight",
				"width_mm",
				"depth_mm",
				"area_mm2",
				"perimeter_mm",
				"ix_mm4",
				"iy_mm4",
				"bar_lengths",
				"dxf_file",
				"section_svg",
				"section_warnings",
			],
			order_by: "series asc, profile_code asc",
			limit_page_length: 500,
		},
		callback(r) {
			state.loading = false;
			state.profiles = r.message || [];
			render_card_grid(listview);
		},
		error() {
			state.loading = false;
		},
	});
}

function clean_dxf_filename(dxfPath) {
	const raw = (dxfPath || "").split("/").pop() || "section.dxf";
	return raw.replace(/([0-9a-f]{6}){1,2}(\.dxf)$/i, "$2");
}

function render_card_grid(listview) {
	const state = listview._card_state;
	const all = state.profiles || [];
	const seriesCounts = { ALL: all.length };
	for (const p of all) {
		const s = p.series || "Other";
		seriesCounts[s] = (seriesCounts[s] || 0) + 1;
	}

	const filtered = all.filter((p) => {
		if (state.series !== "ALL" && p.series !== state.series) return false;
		if (state.role !== "ALL" && p.role !== state.role) return false;
		if (state.search.trim()) {
			const q = state.search.trim().toLowerCase();
			const hay = `${p.profile_code || ""} ${p.profile_name || ""} ${p.series || ""} ${p.role || ""}`.toLowerCase();
			if (!hay.includes(q)) return false;
		}
		return true;
	});

	const seriesKeys = ["ALL", ...Object.keys(seriesCounts).filter((k) => k !== "ALL")];
	const roles = ["ALL", "frame", "sash", "mullion", "bead", "accessory"];

	const seriesTabsHtml = seriesKeys
		.map((s) => {
			const active = state.series === s;
			const label =
				s === "ALL"
					? `All Profiles · ${seriesCounts.ALL}`
					: `${s} · ${seriesCounts[s] || 0}`;
			return `<button type="button" data-series="${frappe.utils.escape_html(s)}" style="border:none;border-bottom:2px solid ${active ? "#0f172a" : "transparent"};background:transparent;padding:8px 14px;font-size:13px;font-weight:${active ? "600" : "500"};color:${active ? "#0f172a" : "#64748b"};cursor:pointer;">${frappe.utils.escape_html(label)}</button>`;
		})
		.join("");

	const rolePillsHtml = roles
		.map((r) => {
			const active = state.role === r;
			const label = r === "ALL" ? "All roles" : r.charAt(0).toUpperCase() + r.slice(1);
			return `<button type="button" data-role="${r}" style="border:1px solid ${active ? "#0f172a" : "#cbd5e1"};background:${active ? "#0f172a" : "#ffffff"};color:${active ? "#ffffff" : "#334155"};border-radius:8px;padding:6px 13px;font-size:12px;font-weight:600;cursor:pointer;">${label}</button>`;
		})
		.join("");

	const cardsHtml = filtered.map((p) => build_profile_card_html(p)).join("");

	listview._$cardContainer.html(`
		<div style="border-bottom:1px solid #e2e8f0;margin-bottom:16px;display:flex;gap:6px;flex-wrap:wrap;">
			${seriesTabsHtml}
		</div>

		<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:20px;">
			<div style="display:flex;gap:8px;flex-wrap:wrap;">
				${rolePillsHtml}
			</div>
			<div style="display:flex;align-items:center;gap:10px;">
				<input type="search" class="fen-card-search" placeholder="Search profiles..." value="${frappe.utils.escape_html(state.search)}" style="border:1px solid #cbd5e1;border-radius:8px;padding:6px 12px;font-size:13px;width:230px;color:#0f172a;background:#ffffff;" />
			</div>
		</div>

		<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:18px;">
			${cardsHtml}
			<div class="fen-add-profile-card" style="border:1.5px dashed #cbd5e1;border-radius:12px;min-height:330px;display:flex;flex-direction:column;align-items:center;justify-content:center;cursor:pointer;color:#64748b;background:#fafafa;transition:border-color 0.15s ease;">
				<div style="font-size:24px;line-height:1;margin-bottom:8px;color:#475569;">+</div>
				<div style="font-size:13px;font-weight:500;color:#475569;">Add a fenestration profile</div>
			</div>
		</div>
	`);

	listview._$cardContainer.find("[data-series]").on("click", function () {
		state.series = $(this).attr("data-series");
		render_card_grid(listview);
	});
	listview._$cardContainer.find("[data-role]").on("click", function () {
		state.role = $(this).attr("data-role");
		render_card_grid(listview);
	});
	listview._$cardContainer.find(".fen-card-search").on("input", function () {
		state.search = $(this).val() || "";
		render_card_grid(listview);
		const input = listview._$cardContainer.find(".fen-card-search")[0];
		if (input) {
			input.focus();
			const len = input.value.length;
			input.setSelectionRange(len, len);
		}
	});
	listview._$cardContainer.find("[data-open-profile]").on("click", function () {
		const name = $(this).attr("data-open-profile");
		frappe.set_route("Form", "Fenestration Profile", name);
	});
	listview._$cardContainer.find("[data-view-details]").on("click", function () {
		const name = $(this).attr("data-view-details");
		const prof = all.find((x) => x.name === name);
		if (prof) open_profile_details_modal(prof);
	});
	listview._$cardContainer.find(".fen-add-profile-card").on("click", () => {
		frappe.new_doc("Fenestration Profile");
	});
}

function build_profile_card_html(p) {
	const codeDisp = (p.profile_code || p.name).replace("-CS400", "");
	const seriesLabel =
		p.series === "CS400"
			? "CS400 Economical"
			: p.series === "CS4800"
			? "CS4800 Premium"
			: p.series || "—";
	const weight =
		p.use_computed_weight && p.computed_kg_per_m ? p.computed_kg_per_m : p.kg_per_m;
	const hasSvg = Boolean(p.section_svg && p.width_mm && p.depth_mm);

	const thumbSvg = hasSvg
		? build_card_thumbnail_svg(p)
		: `<div style="font-size:12px;color:#94a3b8;">No DXF preview</div>`;

	return `
		<article style="border:1px solid #e5e7eb;border-radius:12px;background:#ffffff;overflow:hidden;display:flex;flex-direction:column;box-shadow:0 1px 2px rgba(15,23,42,0.03);">
			<div data-view-details="${frappe.utils.escape_html(p.name)}" style="height:190px;background:#f6f6f4;display:flex;align-items:center;justify-content:center;padding:14px;cursor:pointer;border-bottom:1px solid #f1f5f9;">
				${thumbSvg}
			</div>
			<div style="padding:14px 16px 16px;display:flex;flex-direction:column;flex:1;">
				<div style="display:flex;align-items:baseline;justify-content:space-between;gap:8px;margin-bottom:3px;">
					<div style="font-size:14px;font-weight:700;color:#0f172a;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${frappe.utils.escape_html(codeDisp + " · " + p.profile_name)}">
						${frappe.utils.escape_html(codeDisp)} · ${frappe.utils.escape_html(p.profile_name)}
					</div>
					<span style="font-size:12px;color:#64748b;flex-shrink:0;text-transform:capitalize;">${frappe.utils.escape_html(p.role || "—")}</span>
				</div>
				<div style="font-size:12.5px;color:#64748b;margin-bottom:6px;">
					${frappe.utils.escape_html(seriesLabel)} · Bar ${frappe.utils.escape_html(p.bar_lengths || "4880, 5800")} mm
				</div>
				<div style="display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:12px;">
					<div style="display:flex;align-items:center;gap:6px;font-size:12.5px;color:#475569;">
						<span style="display:inline-block;width:11px;height:11px;border-radius:3px;background:#94a3b8;border:1px solid #64748b;"></span>
						<span>Al 6063-T6 · ${Number(p.width_mm || 0).toFixed(1)} × ${Number(p.depth_mm || 0).toFixed(1)} mm</span>
					</div>
					<span style="padding:2px 9px;border-radius:999px;font-size:11px;font-weight:600;background:${hasSvg ? "#dcfce7" : "#f1f5f9"};color:${hasSvg ? "#15803d" : "#64748b"};">
						${hasSvg ? "OK" : "No DXF"}
					</span>
				</div>
				<div style="border-top:1px solid #f1f5f9;padding-top:10px;margin-top:auto;display:flex;align-items:baseline;justify-content:space-between;margin-bottom:12px;">
					<span style="font-size:12.5px;color:#64748b;">
						${Number(p.area_mm2 || 0).toFixed(1)} mm² · ${Number(p.perimeter_mm || 0).toFixed(0)} mm perim
					</span>
					<span style="font-size:13.5px;font-weight:700;color:#0f172a;">
						${Number(weight || 0).toFixed(3)} kg/m
					</span>
				</div>
				<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
					<button type="button" data-open-profile="${frappe.utils.escape_html(p.name)}" style="border:1px solid #cbd5e1;background:#ffffff;color:#0f172a;border-radius:8px;padding:7px 10px;font-size:12.5px;font-weight:600;cursor:pointer;">
						Edit profile
					</button>
					<button type="button" data-view-details="${frappe.utils.escape_html(p.name)}" style="border:1px solid #cbd5e1;background:#ffffff;color:#0f172a;border-radius:8px;padding:7px 10px;font-size:12.5px;font-weight:600;cursor:pointer;">
						Details
					</button>
				</div>
			</div>
		</article>
	`;
}

function build_card_thumbnail_svg(p) {
	const w = Math.max(Number(p.width_mm) || 10, 1);
	const h = Math.max(Number(p.depth_mm) || 10, 1);

	const cw = 280;
	const ch = 166;
	const padL = 48;
	const padR = 24;
	const padT = 14;
	const padB = 34;
	const availW = cw - padL - padR;
	const availH = ch - padT - padB;

	const s = Math.min(availW / w, availH / h);
	const dw = w * s;
	const dh = h * s;
	const ox = padL + (availW - dw) / 2;
	const oy = padT + (availH - dh) / 2;

	const dimGap = 10;
	const tick = 4;
	const fontSize = 11.5;
	const dimY = oy + dh + dimGap;
	const dimX = ox - dimGap;
	const vTextX = dimX - 11;
	const vTextY = oy + dh / 2;
	const pathStroke = 1.35 / s;

	return `
		<svg viewBox="0 0 ${cw} ${ch}" style="max-width:100%;max-height:166px;width:100%;height:100%;display:block;" xmlns="http://www.w3.org/2000/svg">
			<g transform="translate(${ox.toFixed(2)}, ${oy.toFixed(2)}) scale(${s.toFixed(4)})">
				<path d="${p.section_svg}" fill="#94a3b8" fill-opacity="0.85" stroke="#334155" stroke-width="${pathStroke.toFixed(3)}" stroke-linejoin="round" fill-rule="evenodd" />
			</g>
			<g stroke="#64748b" stroke-width="1" stroke-linecap="square">
				<line x1="${ox.toFixed(2)}" y1="${dimY.toFixed(2)}" x2="${(ox + dw).toFixed(2)}" y2="${dimY.toFixed(2)}" />
				<line x1="${ox.toFixed(2)}" y1="${(dimY - tick).toFixed(2)}" x2="${ox.toFixed(2)}" y2="${(dimY + tick).toFixed(2)}" />
				<line x1="${(ox + dw).toFixed(2)}" y1="${(dimY - tick).toFixed(2)}" x2="${(ox + dw).toFixed(2)}" y2="${(dimY + tick).toFixed(2)}" />

				<line x1="${dimX.toFixed(2)}" y1="${oy.toFixed(2)}" x2="${dimX.toFixed(2)}" y2="${(oy + dh).toFixed(2)}" />
				<line x1="${(dimX - tick).toFixed(2)}" y1="${oy.toFixed(2)}" x2="${(dimX + tick).toFixed(2)}" y2="${oy.toFixed(2)}" />
				<line x1="${(dimX - tick).toFixed(2)}" y1="${(oy + dh).toFixed(2)}" x2="${(dimX + tick).toFixed(2)}" y2="${(oy + dh).toFixed(2)}" />
			</g>
			<text x="${(ox + dw / 2).toFixed(2)}" y="${(dimY + 15).toFixed(2)}" text-anchor="middle" fill="#0f172a" font-size="${fontSize}" font-weight="600" font-family="Inter, system-ui, sans-serif">${Number(p.width_mm).toFixed(1)}</text>
			<text x="${vTextX.toFixed(2)}" y="${vTextY.toFixed(2)}" text-anchor="middle" dominant-baseline="central" fill="#0f172a" font-size="${fontSize}" font-weight="600" font-family="Inter, system-ui, sans-serif" transform="rotate(-90 ${vTextX.toFixed(2)} ${vTextY.toFixed(2)})">${Number(p.depth_mm).toFixed(1)}</text>
		</svg>
	`;
}

function open_profile_details_modal(p) {
	const dxfName = clean_dxf_filename(p.dxf_file);
	const weight =
		p.use_computed_weight && p.computed_kg_per_m ? p.computed_kg_per_m : p.kg_per_m;
	const w = Math.max(Number(p.width_mm) || 10, 1);
	const h = Math.max(Number(p.depth_mm) || 10, 1);
	const span = Math.max(w, h);

	const cw = 640;
	const ch = 310;
	const padL = 72;
	const padR = 52;
	const padT = 26;
	const padB = 54;
	const availW = cw - padL - padR;
	const availH = ch - padT - padB;

	const s = Math.min(availW / w, availH / h);
	const dw = w * s;
	const dh = h * s;
	const ox = padL + (availW - dw) / 2;
	const oy = padT + (availH - dh) / 2;

	const dimGap = 14;
	const tick = 5;
	const fontSize = 12.5;
	const dimY = oy + dh + dimGap;
	const dimX = ox - dimGap;
	const vTextX = dimX - 13;
	const vTextY = oy + dh / 2;
	const pathStroke = 1.5 / s;

	const minorStepMm = span <= 35 ? 1 : span <= 80 ? 2 : 5;
	const minorPx = minorStepMm * s;
	const majorPx = minorPx * 5;

	const d = new frappe.ui.Dialog({
		title: `${(p.profile_code || p.name).replace("-CS400", "")} · ${p.profile_name}`,
		size: "large",
		primary_action_label: __("Open Profile Form"),
		primary_action() {
			d.hide();
			frappe.set_route("Form", "Fenestration Profile", p.name);
		},
	});

	d.$body.html(`
		<div style="padding:6px 4px;">
			<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
				<div style="font-size:13px;color:#64748b;">
					Series: <strong style="color:#0f172a;">${frappe.utils.escape_html(p.series)}</strong> · Role: <strong style="color:#0f172a;text-transform:capitalize;">${frappe.utils.escape_html(p.role)}</strong> · DXF: <code>${frappe.utils.escape_html(dxfName)}</code>
				</div>
				<span style="padding:3px 10px;border-radius:999px;background:#dcfce7;color:#15803d;font-size:12px;font-weight:600;">Parsed</span>
			</div>
			<div style="border:1px solid #e2e8f0;border-radius:10px;background:#f8fafc;overflow:hidden;margin-bottom:16px;">
				<svg viewBox="0 0 ${cw} ${ch}" style="width:100%;height:310px;display:block;" xmlns="http://www.w3.org/2000/svg">
					<defs>
						<pattern id="modal-grid-min" width="${minorPx.toFixed(3)}" height="${minorPx.toFixed(3)}" patternUnits="userSpaceOnUse" patternTransform="translate(${ox.toFixed(2)}, ${oy.toFixed(2)})">
							<path d="M ${minorPx.toFixed(3)} 0 L 0 0 0 ${minorPx.toFixed(3)}" fill="none" stroke="#e2e8f0" stroke-width="0.7" />
						</pattern>
						<pattern id="modal-grid-maj" width="${majorPx.toFixed(3)}" height="${majorPx.toFixed(3)}" patternUnits="userSpaceOnUse" patternTransform="translate(${ox.toFixed(2)}, ${oy.toFixed(2)})">
							<rect width="${majorPx.toFixed(3)}" height="${majorPx.toFixed(3)}" fill="url(#modal-grid-min)" />
							<path d="M ${majorPx.toFixed(3)} 0 L 0 0 0 ${majorPx.toFixed(3)}" fill="none" stroke="#cbd5e1" stroke-width="1.1" />
						</pattern>
					</defs>
					<rect x="0" y="0" width="${cw}" height="${ch}" fill="url(#modal-grid-maj)" />
					<g transform="translate(${ox.toFixed(2)}, ${oy.toFixed(2)}) scale(${s.toFixed(4)})">
						<path d="${p.section_svg || ""}" fill="#94a3b8" fill-opacity="0.86" stroke="#1e293b" stroke-width="${pathStroke.toFixed(3)}" stroke-linejoin="round" fill-rule="evenodd" />
					</g>
					<g stroke="#475569" stroke-width="1.15" stroke-linecap="square">
						<line x1="${ox.toFixed(2)}" y1="${dimY.toFixed(2)}" x2="${(ox + dw).toFixed(2)}" y2="${dimY.toFixed(2)}" />
						<line x1="${ox.toFixed(2)}" y1="${(dimY - tick).toFixed(2)}" x2="${ox.toFixed(2)}" y2="${(dimY + tick).toFixed(2)}" />
						<line x1="${(ox + dw).toFixed(2)}" y1="${(dimY - tick).toFixed(2)}" x2="${(ox + dw).toFixed(2)}" y2="${(dimY + tick).toFixed(2)}" />
						<line x1="${dimX.toFixed(2)}" y1="${oy.toFixed(2)}" x2="${dimX.toFixed(2)}" y2="${(oy + dh).toFixed(2)}" />
						<line x1="${(dimX - tick).toFixed(2)}" y1="${oy.toFixed(2)}" x2="${(dimX + tick).toFixed(2)}" y2="${oy.toFixed(2)}" />
						<line x1="${(dimX - tick).toFixed(2)}" y1="${(oy + dh).toFixed(2)}" x2="${(dimX + tick).toFixed(2)}" y2="${(oy + dh).toFixed(2)}" />
					</g>
					<text x="${(ox + dw / 2).toFixed(2)}" y="${(dimY + 18).toFixed(2)}" text-anchor="middle" fill="#0f172a" font-size="${fontSize}" font-weight="600" font-family="Inter, system-ui, sans-serif">${Number(p.width_mm).toFixed(1)}</text>
					<text x="${vTextX.toFixed(2)}" y="${vTextY.toFixed(2)}" text-anchor="middle" dominant-baseline="central" fill="#0f172a" font-size="${fontSize}" font-weight="600" font-family="Inter, system-ui, sans-serif" transform="rotate(-90 ${vTextX.toFixed(2)} ${vTextY.toFixed(2)})">${Number(p.depth_mm).toFixed(1)}</text>
				</svg>
			</div>
			<div style="display:grid;grid-template-columns:repeat(2,1fr);gap:16px 36px;">
				<div><div style="font-size:12px;color:#64748b;">Section area</div><div style="font-size:17px;font-weight:700;color:#0f172a;">${Number(p.area_mm2 || 0).toFixed(1)} mm²</div></div>
				<div><div style="font-size:12px;color:#64748b;">Weight</div><div style="font-size:17px;font-weight:700;color:#0f172a;">${Number(weight || 0).toFixed(3)} kg/m</div></div>
				<div><div style="font-size:12px;color:#64748b;">Width × depth</div><div style="font-size:17px;font-weight:700;color:#0f172a;">${Number(p.width_mm || 0).toFixed(1)} × ${Number(p.depth_mm || 0).toFixed(1)} mm</div></div>
				<div><div style="font-size:12px;color:#64748b;">Perimeter</div><div style="font-size:17px;font-weight:700;color:#0f172a;">${Number(p.perimeter_mm || 0).toFixed(1)} mm</div></div>
				<div><div style="font-size:12px;color:#64748b;">Ix / Iy</div><div style="font-size:16px;font-weight:700;color:#0f172a;">${Math.round(p.ix_mm4 || 0).toLocaleString("en-IN")} / ${Math.round(p.iy_mm4 || 0).toLocaleString("en-IN")} mm⁴</div></div>
				<div><div style="font-size:12px;color:#64748b;">Material</div><div style="font-size:16px;font-weight:700;color:#0f172a;">Al 6063-T6</div></div>
			</div>
		</div>
	`);
	d.show();
}

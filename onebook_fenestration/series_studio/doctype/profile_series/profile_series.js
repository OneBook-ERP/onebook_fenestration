frappe.ui.form.on("Profile Series", {
	refresh(frm) {
		frm.add_custom_button(__("All Profiles (Card View)"), () => {
			window.localStorage.setItem("fen_profile_view_mode", "card");
			frappe.set_route("List", "Fenestration Profile");
		});
		render_series_profiles_card_view(frm);
	},
});

function render_series_profiles_card_view(frm) {
	const field = frm.fields_dict.profiles_preview;
	if (!field || !field.$wrapper) return;
	if (frm.is_new()) {
		field.$wrapper.html(`<div style="color:#64748b;font-size:13px;padding:12px 0;">Save the series to view its profiles.</div>`);
		return;
	}

	frappe.call({
		method: "frappe.client.get_list",
		args: {
			doctype: "Fenestration Profile",
			filters: { series: frm.doc.name },
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
			],
			order_by: "profile_code asc",
			limit_page_length: 200,
		},
		callback(r) {
			const profiles = r.message || [];
			const state = frm._series_card_state || { role: "ALL", search: "" };
			frm._series_card_state = state;
			draw_series_cards(frm, field.$wrapper, profiles, state);
		},
	});
}

function draw_series_cards(frm, $wrapper, profiles, state) {
	const roles = ["ALL", "frame", "sash", "mullion", "bead", "accessory"];
	const filtered = profiles.filter((p) => {
		if (state.role !== "ALL" && p.role !== state.role) return false;
		if (state.search.trim()) {
			const q = state.search.trim().toLowerCase();
			const hay = `${p.profile_code || ""} ${p.profile_name || ""} ${p.role || ""}`.toLowerCase();
			if (!hay.includes(q)) return false;
		}
		return true;
	});

	const rolePills = roles
		.map((r) => {
			const active = state.role === r;
			const label = r === "ALL" ? `All · ${profiles.length}` : r.charAt(0).toUpperCase() + r.slice(1);
			return `<button type="button" data-role="${r}" style="border:1px solid ${active ? "#0f172a" : "#cbd5e1"};background:${active ? "#0f172a" : "#ffffff"};color:${active ? "#ffffff" : "#334155"};border-radius:8px;padding:5px 12px;font-size:12px;font-weight:600;cursor:pointer;">${label}</button>`;
		})
		.join("");

	const cards = filtered
		.map((p) => {
			const codeDisp = (p.profile_code || p.name).replace("-CS400", "");
			const weight = p.use_computed_weight && p.computed_kg_per_m ? p.computed_kg_per_m : p.kg_per_m;
			const hasSvg = Boolean(p.section_svg && p.width_mm && p.depth_mm);
			const w = Math.max(Number(p.width_mm) || 10, 1);
			const h = Math.max(Number(p.depth_mm) || 10, 1);
			const span = Math.max(w, h);
			const padL = span * 0.28;
			const padB = span * 0.26;
			const padT = span * 0.12;
			const padR = span * 0.14;
			const strokeW = Math.max(span * 0.011, 0.22);
			const fontSize = Math.max(span * 0.095, 2.5);
			const dimOffset = span * 0.11;

			const svg = hasSvg
				? `<svg viewBox="${(-padL).toFixed(2)} ${(-padT).toFixed(2)} ${(w + padL + padR).toFixed(2)} ${(h + padT + padB).toFixed(2)}" style="max-width:100%;max-height:155px;width:100%;height:100%;display:block;" xmlns="http://www.w3.org/2000/svg">
						<path d="${p.section_svg}" fill="#94a3b8" fill-opacity="0.85" stroke="#334155" stroke-width="${strokeW.toFixed(3)}" stroke-linejoin="round" fill-rule="evenodd" />
						<text x="${(w / 2).toFixed(2)}" y="${(h + dimOffset + fontSize * 0.85).toFixed(2)}" text-anchor="middle" fill="#0f172a" font-size="${fontSize.toFixed(2)}" font-weight="600">${Number(p.width_mm).toFixed(1)}</text>
						<text x="${(-dimOffset - fontSize * 0.35).toFixed(2)}" y="${(h / 2).toFixed(2)}" text-anchor="middle" fill="#0f172a" font-size="${fontSize.toFixed(2)}" font-weight="600" transform="rotate(-90 ${(-dimOffset - fontSize * 0.35).toFixed(2)} ${(h / 2).toFixed(2)})">${Number(p.depth_mm).toFixed(1)}</text>
					</svg>`
				: `<div style="font-size:12px;color:#94a3b8;">No DXF</div>`;

			return `
				<article style="border:1px solid #e5e7eb;border-radius:12px;background:#ffffff;overflow:hidden;display:flex;flex-direction:column;">
					<div data-open="${frappe.utils.escape_html(p.name)}" style="height:180px;background:#f6f6f4;display:flex;align-items:center;justify-content:center;padding:12px;cursor:pointer;border-bottom:1px solid #f1f5f9;">
						${svg}
					</div>
					<div style="padding:14px 16px;display:flex;flex-direction:column;flex:1;">
						<div style="display:flex;align-items:baseline;justify-content:space-between;gap:8px;margin-bottom:3px;">
							<div style="font-size:14px;font-weight:700;color:#0f172a;">${frappe.utils.escape_html(codeDisp)} · ${frappe.utils.escape_html(p.profile_name)}</div>
							<span style="font-size:12px;color:#64748b;text-transform:capitalize;">${frappe.utils.escape_html(p.role || "—")}</span>
						</div>
						<div style="font-size:12.5px;color:#64748b;margin-bottom:8px;">
							${Number(p.width_mm || 0).toFixed(1)} × ${Number(p.depth_mm || 0).toFixed(1)} mm · Bar ${frappe.utils.escape_html(p.bar_lengths || "4880, 5800")} mm
						</div>
						<div style="border-top:1px solid #f1f5f9;padding-top:10px;margin-top:auto;display:flex;align-items:baseline;justify-content:space-between;margin-bottom:10px;">
							<span style="font-size:12px;color:#64748b;">${Number(p.area_mm2 || 0).toFixed(1)} mm² · ${Number(p.perimeter_mm || 0).toFixed(0)} mm</span>
							<span style="font-size:13.5px;font-weight:700;color:#0f172a;">${Number(weight || 0).toFixed(3)} kg/m</span>
						</div>
						<button type="button" data-open="${frappe.utils.escape_html(p.name)}" style="border:1px solid #cbd5e1;background:#ffffff;color:#0f172a;border-radius:8px;padding:7px 10px;font-size:12.5px;font-weight:600;cursor:pointer;width:100%;">
							Open profile
						</button>
					</div>
				</article>
			`;
		})
		.join("");

	$wrapper.html(`
		<div style="margin-top:6px;">
			<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;margin-bottom:16px;">
				<div style="display:flex;gap:8px;flex-wrap:wrap;">${rolePills}</div>
				<input type="search" class="fen-series-search" placeholder="Search series profiles..." value="${frappe.utils.escape_html(state.search)}" style="border:1px solid #cbd5e1;border-radius:8px;padding:6px 12px;font-size:13px;width:220px;" />
			</div>
			<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(285px,1fr));gap:16px;">
				${cards}
			</div>
		</div>
	`);

	$wrapper.find("[data-role]").on("click", function () {
		state.role = $(this).attr("data-role");
		draw_series_cards(frm, $wrapper, profiles, state);
	});
	$wrapper.find(".fen-series-search").on("input", function () {
		state.search = $(this).val() || "";
		draw_series_cards(frm, $wrapper, profiles, state);
		const input = $wrapper.find(".fen-series-search")[0];
		if (input) {
			input.focus();
			const len = input.value.length;
			input.setSelectionRange(len, len);
		}
	});
	$wrapper.find("[data-open]").on("click", function () {
		frappe.set_route("Form", "Fenestration Profile", $(this).attr("data-open"));
	});
}


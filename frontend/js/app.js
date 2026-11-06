// Empty for the local same-origin FastAPI app; set in config.js for Netlify.
const API_BASE = (window.LEAD_SCORING_API_URL || "").replace(/\/+$/, "");

// Max points per scoring criterion, mirroring backend/rules/scoring_rules.json.
// Used ONLY to render the visual breakdown bars - the backend remains the
// single source of truth for the actual awarded score.
const BREAKDOWN_MAX = {
  target_industry: 20,
  decision_maker: 15,
  company_size: 10,
  pain_point: 20,
  buying_signal: 20,
  automation_opportunity: 10,
  recent_activity: 5,
};

const form = document.getElementById("leadForm");
const submitBtn = document.getElementById("submitBtn");
const submitLabel = document.getElementById("submitLabel");
const submitSpinner = document.getElementById("submitSpinner");
const formError = document.getElementById("formError");
const leadDrawer = document.getElementById("leadDetailDrawer");
const leadDrawerBackdrop = document.getElementById("leadDrawerBackdrop");
const drawerCloseBtn = document.getElementById("drawerCloseBtn");
const drawerBody = document.getElementById("drawerBody");
let lastResultData = null;
let currentLeadFilter = "all";

const resultEmpty = document.getElementById("resultEmpty");
const resultContent = document.getElementById("resultContent");
const cachedBanner = document.getElementById("cachedBanner");

const sapSection = document.getElementById("sapSection");

const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");

// --- Recent Activity toggle state (boolean, defaults to No/false) ---
let recentActivityValue = false;
const raYesBtn = document.getElementById("raYes");
const raNoBtn = document.getElementById("raNo");

function setRecentActivity(value) {
  recentActivityValue = value;
  raYesBtn.classList.toggle("active", value === true);
  raNoBtn.classList.toggle("active", value === false);
}
raYesBtn.addEventListener("click", () => setRecentActivity(true));
raNoBtn.addEventListener("click", () => setRecentActivity(false));

async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    const data = await res.json();
    if (data.llm_enabled) {
      statusDot.className = "dot online";
      statusText.textContent = `AI live · ${data.ai_provider}`;
    } else {
      statusDot.className = "dot offline";
      statusText.textContent = `AI offline · using fallback`;
    }
  } catch (e) {
    statusDot.className = "dot offline";
    statusText.textContent = "Engine unreachable";
  }
}

function fieldValue(id) {
  const el = document.getElementById(id);
  const v = el.value.trim();
  return v === "" ? null : v;
}

function buildPayload() {
  const sizeRaw = fieldValue("company_size");
  return {
    name: fieldValue("name"),
    company: fieldValue("company"),
    job_title: fieldValue("job_title"),
    country: fieldValue("country"),
    industry: fieldValue("industry"),
    company_size: sizeRaw !== null ? parseInt(sizeRaw, 10) : null,
    website: fieldValue("website"),
    linkedin: fieldValue("linkedin"),
    pain_point: fieldValue("pain_point"),
    buying_signal: fieldValue("buying_signal"),
    custom_offer: fieldValue("custom_offer"), // optional - auto-generated server-side if null
    recent_activity: recentActivityValue, // boolean, never a string
  };
}

function setLoading(isLoading) {
  submitBtn.disabled = isLoading;
  submitLabel.textContent = isLoading ? "Analyzing lead with AI..." : "Analyze Lead";
  submitSpinner.hidden = !isLoading;
}

function showError(message) {
  formError.textContent = message;
  formError.hidden = false;
}

function clearError() {
  formError.hidden = true;
  formError.textContent = "";
}

function setFieldValidity(fieldId, isInvalid, message = "") {
  const el = document.getElementById(fieldId);
  if (!el) return;
  el.classList.toggle("is-invalid", isInvalid);
  el.setAttribute("aria-invalid", String(isInvalid));
  if (message) {
    el.setAttribute("data-error", message);
  } else {
    el.removeAttribute("data-error");
  }
}

function clearFieldValidity() {
  ["name", "company", "company_size", "website", "linkedin"].forEach((fieldId) => {
    setFieldValidity(fieldId, false);
  });
}

function validateFormPayload(payload) {
  clearFieldValidity();

  const invalidFields = [];
  if (!payload.name) {
    invalidFields.push(["name", "Lead name is required."]);
  }
  if (!payload.company) {
    invalidFields.push(["company", "Company name is required."]);
  }
  if (payload.company_size !== null && (Number.isNaN(payload.company_size) || payload.company_size < 0)) {
    invalidFields.push(["company_size", "Company size must be a valid non-negative number."]);
  }
  if (payload.website && !/^https?:\/\//i.test(payload.website)) {
    invalidFields.push(["website", "Website should start with http:// or https://."]);
  }
  if (payload.linkedin && !/^https?:\/\//i.test(payload.linkedin) && !/linkedin\.com\//i.test(payload.linkedin)) {
    invalidFields.push(["linkedin", "LinkedIn should be a valid URL."]);
  }

  if (invalidFields.length) {
    invalidFields.forEach(([fieldId, message]) => setFieldValidity(fieldId, true, message));
    const firstError = invalidFields[0][1];
    showError(firstError);
    return false;
  }

  return true;
}

function classificationClass(cls) {
  if (!cls) return "";
  return cls.toLowerCase();
}

function formatDate(iso) {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  } catch (e) {
    return "—";
  }
}

function renderList(el, items) {
  el.innerHTML = "";
  (items || []).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    el.appendChild(li);
  });
}

function renderBreakdown(breakdown) {
  const el = document.getElementById("resBreakdown");
  el.innerHTML = "";
  let total = 0;
  Object.entries(breakdown || {}).forEach(([key, value]) => {
    const max = BREAKDOWN_MAX[key] ?? value;
    total += value;
    const label = key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
    const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;

    const row = document.createElement("div");
    row.className = "breakdown-bar-row";
    row.innerHTML = `
      <div class="breakdown-bar-label">
        <span>${label}</span>
        <strong>${value}/${max}</strong>
      </div>
      <div class="breakdown-bar-track">
        <div class="breakdown-bar-fill" style="width:${pct}%"></div>
      </div>
    `;
    el.appendChild(row);
  });

  const totalRow = document.createElement("div");
  totalRow.className = "breakdown-total-row";
  totalRow.innerHTML = `<span>Total</span><strong>${total}/100</strong>`;
  el.appendChild(totalRow);
}

function openLeadDrawer(item) {
  const q = item.qualification || {};
  const websiteResearch = q.website_research;
  const hasWebsiteResearch = typeof websiteResearch?.summary === "string" && websiteResearch.summary.trim();
  const drawerTitle = document.getElementById("drawerTitle");
  drawerTitle.textContent = `${item.name} · ${item.company}`;
  leadDrawer.dataset.leadId = String(item.id);
  drawerBody.innerHTML = `
    <div class="drawer-summary">
      <div>
        <strong>${item.name}</strong>
        <span>${item.company}</span>
      </div>
      <div class="history-badge ${q.classification ? classificationClass(q.classification) : ""}">${q.classification || "Pending"}</div>
    </div>

    <div class="drawer-meta-grid">
      <div class="drawer-meta-item"><small>Job title</small><strong>${item.job_title || "—"}</strong></div>
      <div class="drawer-meta-item"><small>Score</small><strong>${q.score ? q.score + "/100" : "—"}</strong></div>
      <div class="drawer-meta-item"><small>Country</small><strong>${item.country || "—"}</strong></div>
      <div class="drawer-meta-item"><small>ICP fit</small><strong>${q.icp_fit !== undefined ? (q.icp_fit ? "Strong" : "Not fit") : "—"}</strong></div>
    </div>

    <div class="field drawer-status-field">
      <label for="drawerLeadStatus">Sales status</label>
      <select id="drawerLeadStatus">
        ${["New", "Contacted", "Qualified", "Disqualified", "Converted"].map((status) =>
          `<option value="${status}" ${status === (item.status || "New") ? "selected" : ""}>${status}</option>`
        ).join("")}
      </select>
    </div>

    <section class="drawer-card-section">
      <h4>Qualification history</h4>
      <p class="history-loading" id="qualificationHistoryLoading">Loading previous runs…</p>
      <ul id="qualificationHistoryList" class="qualification-history-list"></ul>
    </section>

    ${hasWebsiteResearch ? `
      <div class="drawer-card-section website-research-section">
        <h4>Website Research</h4>
        <p class="website-research-summary"></p>
        <ul class="website-research-sources" aria-label="Website research sources"></ul>
      </div>
    ` : ""}

    <div class="drawer-card-section">
      <h4>Reason</h4>
      <p>${q.reason || "No qualification summary available yet."}</p>
    </div>

    <div class="drawer-card-section">
      <h4>Recommended offer</h4>
      <p>${q.recommended_offer || "—"}</p>
    </div>

    <div class="drawer-card-section">
      <h4>Next action</h4>
      <p>${q.next_action || "—"}</p>
    </div>

    <div class="drawer-card-section">
      <h4>Recent activity</h4>
      <p>${item.recent_activity ? "Yes" : "No"}</p>
    </div>

    <div class="drawer-actions">
      <button type="button" class="btn-primary drawer-edit-trigger">Edit lead</button>
      <button type="button" class="btn-ghost drawer-delete-trigger">Delete</button>
    </div>

    <form id="drawerEditForm" class="drawer-edit-form">
      <div class="grid-2">
        <div class="field">
          <label for="drawerName">Lead Name</label>
          <input type="text" id="drawerName" name="name" value="${escapeHtml(item.name || "")}" required />
        </div>
        <div class="field">
          <label for="drawerCompany">Company</label>
          <input type="text" id="drawerCompany" name="company" value="${escapeHtml(item.company || "")}" required />
        </div>
      </div>
      <div class="grid-2">
        <div class="field">
          <label for="drawerJobTitle">Job Title</label>
          <input type="text" id="drawerJobTitle" name="job_title" value="${escapeHtml(item.job_title || "")}" />
        </div>
        <div class="field">
          <label for="drawerCountry">Country</label>
          <input type="text" id="drawerCountry" name="country" value="${escapeHtml(item.country || "")}" />
        </div>
      </div>
      <div class="grid-2">
        <div class="field">
          <label for="drawerIndustry">Industry</label>
          <input type="text" id="drawerIndustry" name="industry" value="${escapeHtml(item.industry || "")}" />
        </div>
        <div class="field">
          <label for="drawerCompanySize">Company Size</label>
          <input type="number" id="drawerCompanySize" name="company_size" value="${item.company_size || ""}" min="1" />
        </div>
      </div>
      <div class="field">
        <label for="drawerWebsite">Website</label>
        <input type="text" id="drawerWebsite" name="website" value="${escapeHtml(item.website || "")}" />
      </div>
      <div class="field">
        <label for="drawerLinkedin">LinkedIn</label>
        <input type="text" id="drawerLinkedin" name="linkedin" value="${escapeHtml(item.linkedin || "")}" />
      </div>
      <div class="field">
        <label for="drawerPainPoint">Pain Point</label>
        <textarea id="drawerPainPoint" name="pain_point" rows="2">${escapeHtml(item.pain_point || "")}</textarea>
      </div>
      <div class="field">
        <label for="drawerBuyingSignal">Buying Signal</label>
        <textarea id="drawerBuyingSignal" name="buying_signal" rows="2">${escapeHtml(item.buying_signal || "")}</textarea>
      </div>
      <div class="field">
        <label>Recent Activity</label>
        <div class="toggle-group" role="group" aria-label="Recent activity edit">
          <button type="button" class="toggle-btn ${item.recent_activity ? "active" : ""}" data-drawer-toggle="true">Yes</button>
          <button type="button" class="toggle-btn ${!item.recent_activity ? "active" : ""}" data-drawer-toggle="false">No</button>
        </div>
        <input type="hidden" id="drawerRecentActivity" name="recent_activity" value="${item.recent_activity ? "true" : "false"}" />
      </div>
      <div class="drawer-actions">
        <button type="submit" class="btn-primary">Save changes</button>
        <button type="button" class="btn-ghost" data-drawer-cancel>Cancel</button>
      </div>
    </form>
  `;

  const researchSection = drawerBody.querySelector(".website-research-section");
  if (researchSection) {
    researchSection.querySelector(".website-research-summary").textContent = websiteResearch.summary;
    const sourceList = researchSection.querySelector(".website-research-sources");
    (Array.isArray(websiteResearch.sources) ? websiteResearch.sources : []).forEach((source) => {
      if (typeof source !== "string") return;
      let parsedUrl;
      try {
        parsedUrl = new URL(source);
      } catch {
        return;
      }
      if (parsedUrl.protocol !== "http:" && parsedUrl.protocol !== "https:") return;

      const itemElement = document.createElement("li");
      const link = document.createElement("a");
      link.href = parsedUrl.href;
      link.textContent = `${parsedUrl.hostname}${parsedUrl.pathname === "/" ? "" : parsedUrl.pathname}`;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      itemElement.appendChild(link);
      sourceList.appendChild(itemElement);
    });
    sourceList.hidden = sourceList.childElementCount === 0;
  }

  const editForm = document.getElementById("drawerEditForm");
  const statusSelect = document.getElementById("drawerLeadStatus");
  statusSelect.addEventListener("change", async () => {
    const previousStatus = item.status || "New";
    statusSelect.disabled = true;
    try {
      const response = await fetch(`${API_BASE}/leads/${item.id}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: statusSelect.value }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(result.detail || "Unable to update this lead's status.");
      }
      item.status = result.lead.status;
      await loadHistory();
    } catch (err) {
      statusSelect.value = previousStatus;
      alert(err.message || "Unable to update this lead's status.");
    } finally {
      statusSelect.disabled = false;
    }
  });

  const drawerEditTrigger = document.querySelector(".drawer-edit-trigger");
  const deleteTrigger = document.querySelector(".drawer-delete-trigger");
  const cancelButton = document.querySelector("[data-drawer-cancel]");

  drawerEditTrigger.addEventListener("click", () => editForm.classList.add("open"));
  cancelButton.addEventListener("click", () => editForm.classList.remove("open"));
  deleteTrigger.addEventListener("click", async () => {
    await deleteLead(item.id, item.name);
    closeLeadDrawer();
  });

  document.querySelectorAll("[data-drawer-toggle]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const val = btn.dataset.drawerToggle === "true";
      document.getElementById("drawerRecentActivity").value = String(val);
      document.querySelectorAll("[data-drawer-toggle]").forEach((b) => b.classList.toggle("active", b.dataset.drawerToggle === String(val)));
    });
  });

  editForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = {
      name: document.getElementById("drawerName").value.trim(),
      company: document.getElementById("drawerCompany").value.trim(),
      job_title: document.getElementById("drawerJobTitle").value.trim() || null,
      country: document.getElementById("drawerCountry").value.trim() || null,
      industry: document.getElementById("drawerIndustry").value.trim() || null,
      company_size: document.getElementById("drawerCompanySize").value ? parseInt(document.getElementById("drawerCompanySize").value, 10) : null,
      website: document.getElementById("drawerWebsite").value.trim() || null,
      linkedin: document.getElementById("drawerLinkedin").value.trim() || null,
      pain_point: document.getElementById("drawerPainPoint").value.trim() || null,
      buying_signal: document.getElementById("drawerBuyingSignal").value.trim() || null,
      recent_activity: document.getElementById("drawerRecentActivity").value === "true",
      custom_offer: item.custom_offer || null,
    };

    try {
      const response = await fetch(`${API_BASE}/leads/${item.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(result.detail || "Unable to update this lead.");
      }
      await loadHistory();
      renderResult({ lead: result.lead, qualification: result.qualification }, { cached: false });
      openLeadDrawer({ ...result.lead, qualification: result.qualification });
      if (result.qualification) {
        lastResultData = { lead: result.lead, qualification: result.qualification };
      }
    } catch (err) {
      alert(err.message || "Unable to update this lead.");
    }
  });

  leadDrawer.classList.add("open");
  leadDrawer.setAttribute("aria-hidden", "false");
  leadDrawerBackdrop.hidden = false;
  loadQualificationHistory(item.id);
}

async function loadQualificationHistory(leadId) {
  const list = document.getElementById("qualificationHistoryList");
  const loading = document.getElementById("qualificationHistoryLoading");
  if (!list || !loading) return;
  list.replaceChildren();
  loading.hidden = false;
  loading.textContent = "Loading previous runs…";
  try {
    const response = await fetch(`${API_BASE}/leads/${leadId}/qualification-history`);
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "Unable to load qualification history.");
    }
    if (leadDrawer.dataset.leadId !== String(leadId)) return;
    loading.hidden = true;
    if (!data.history.length) {
      loading.hidden = false;
      loading.textContent = "No qualification history available.";
      return;
    }
    data.history.forEach((run) => {
      const entry = document.createElement("li");
      const title = document.createElement("strong");
      title.textContent = `${formatDate(run.created_at)} · ${run.qualification.classification} · ${run.qualification.score}/100`;
      const reason = document.createElement("p");
      reason.textContent = run.qualification.reason || "No qualification summary available.";
      const version = document.createElement("small");
      version.textContent = `Rules ${run.rules_version.slice(0, 12)}`;
      entry.append(title, reason, version);
      list.appendChild(entry);
    });
  } catch (err) {
    if (leadDrawer.dataset.leadId !== String(leadId)) return;
    loading.hidden = false;
    loading.textContent = err.message || "Unable to load qualification history.";
  }
}

function closeLeadDrawer() {
  leadDrawer.classList.remove("open");
  leadDrawer.setAttribute("aria-hidden", "true");
  leadDrawerBackdrop.hidden = true;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function renderResult(data, options = {}) {
  const lead = data.lead;
  const q = data.qualification;
  lastResultData = data;

  cachedBanner.hidden = !options.cached;

  document.getElementById("resNameCompany").textContent = `${lead.name} · ${lead.company}`;
  document.getElementById("resTitleCountry").textContent =
    [lead.job_title, lead.country].filter(Boolean).join(" · ") || "—";

  document.getElementById("scoreValue").textContent = q.score;

  const tag = document.getElementById("classificationTag");
  tag.textContent = q.classification;
  tag.className = "classification-tag " + classificationClass(q.classification);

  const icpTag = document.getElementById("icpTag");
  icpTag.textContent = q.icp_fit ? "ICP Fit: Strong" : "ICP Fit: Not Fit";
  icpTag.className = "icp-tag" + (q.icp_fit ? " fit" : "");

  document.getElementById("buyingIntentChip").textContent = `Buying Intent: ${q.buying_intent || "—"}`;

  renderList(document.getElementById("resMatchedCriteria"), q.matched_criteria);
  renderList(document.getElementById("resMissingCriteria"), q.failed_criteria);

  document.getElementById("resReason").textContent = q.reason;

  // Recent Activity is a plain boolean; the actual explanation lives in the
  // buying_signal free-text field, kept separate per the scoring design.
  const activityFlag = document.getElementById("resActivityFlag");
  if (lead.recent_activity) {
    activityFlag.textContent = "✓ Yes";
    activityFlag.className = "activity-flag yes";
  } else {
    activityFlag.textContent = "✕ No";
    activityFlag.className = "activity-flag no";
  }
  document.getElementById("resBuyingSignalNote").textContent =
    lead.buying_signal ? `Buying Signal: "${lead.buying_signal}"` : "No buying signal notes provided.";

  renderList(document.getElementById("resPainPoints"), q.pain_points);
  renderList(document.getElementById("resBuyingSignals"), q.buying_signals);

  document.getElementById("resOffer").textContent = q.recommended_offer;
  document.getElementById("resNextAction").textContent = q.next_action;
  document.getElementById("resRecommendedTeam").textContent = q.recommended_team || "—";
  document.getElementById("resExpectedRevenue").textContent = q.expected_revenue || "—";
  document.getElementById("resProbability").textContent = q.probability || "—";

  renderBreakdown(q.scoring_breakdown);

  const source = q.ai_assessment?.assessment_source || "unknown";
  document.getElementById("resMeta").innerHTML =
    `<span>Lead ID: ${lead.id}</span><span>Assessment source: ${source}</span>`;

  resultEmpty.hidden = true;
  resultContent.hidden = false;

  renderSalesActionPlan(q.sales_action_plan, lead.id);
}

function renderSapList(elId, items) {
  const el = document.getElementById(elId);
  el.innerHTML = "";
  (items || []).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    el.appendChild(li);
  });
}

function renderSalesActionPlan(plan, leadId) {
  if (!plan) {
    sapSection.hidden = true;
    return;
  }

  document.getElementById("sapNextActionText").textContent = plan.next_action || "—";
  document.getElementById("sapApproachText").textContent = plan.approach || "—";
  document.getElementById("sapCommStrategyText").textContent = plan.communication_strategy || "—";
  document.getElementById("sapMeetingObjectiveText").textContent = plan.meeting_objective || "—";
  document.getElementById("sapOfferText").textContent = plan.recommended_offer || "—";
  document.getElementById("sapFollowUpText").textContent = plan.follow_up_plan || "—";

  renderSapList("sapTalkingPointsList", plan.talking_points);
  renderSapList("sapDiscoveryQuestionsList", plan.discovery_questions);
  renderSapList("sapPainPointsList", plan.pain_points_to_validate);
  renderSapList("sapTeamList", plan.recommended_team);
  renderSapList("sapObjectionsList", plan.possible_objections);
  renderSapList("sapObjectionHandlingList", plan.objection_handling);
  renderSapList("sapAfterMeetingList", plan.after_meeting_actions);
  renderSapList("sapInfoToCollectList", plan.information_to_collect);
  renderSapList("sapSuccessCriteriaList", plan.success_criteria);

  const source = plan.assessment_source || "unknown";
  document.getElementById("sapMeta").innerHTML =
    `<span>Lead ID: ${leadId}</span><span>Plan source: ${source}</span>`;

  sapSection.hidden = false;
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearError();

  const payload = buildPayload();
  if (!validateFormPayload(payload)) {
    return;
  }

  setLoading(true);
  try {
    const res = await fetch(`${API_BASE}/qualify-lead`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      const detail = Array.isArray(errBody.detail)
        ? errBody.detail.map((d) => d.msg).join("; ")
        : errBody.detail || "Unable to qualify this lead. Please try again.";
      throw new Error(detail);
    }

    const data = await res.json();
    renderResult(data, { cached: !!data.cached });
    loadHistory();
  } catch (err) {
    showError(err.message || "Unable to qualify this lead. Please try again.");
  } finally {
    setLoading(false);
  }
});

["name", "company", "company_size", "website", "linkedin"].forEach((fieldId) => {
  const el = document.getElementById(fieldId);
  if (!el) return;
  el.addEventListener("input", () => {
    setFieldValidity(fieldId, false);
    if (!formError.hidden) {
      clearError();
    }
  });
});

function updateStats(leads) {
  const total = leads.length;
  let hot = 0, warm = 0, cold = 0;
  leads.forEach((item) => {
    const cls = item.qualification?.classification;
    if (cls === "HOT") hot += 1;
    else if (cls === "WARM") warm += 1;
    else if (cls === "COLD") cold += 1;
  });
  document.getElementById("statTotal").textContent = total;
  document.getElementById("statHot").textContent = hot;
  document.getElementById("statWarm").textContent = warm;
  document.getElementById("statCold").textContent = cold;
}

function buildLeadCard(item) {
  const q = item.qualification;
  const card = document.createElement("div");
  card.className = "lead-card lead-card-clickable";
  card.title = "View lead details and sales action plan";

  const metaBits = [item.job_title, item.industry, item.company_size ? `${item.company_size} employees` : null]
    .filter(Boolean)
    .join(" · ");

  card.innerHTML = `
    <div class="lead-card-top">
      <div>
        <div class="lead-card-name">${item.name}</div>
        <div class="lead-card-company">${item.company}</div>
      </div>
      <div class="lead-card-score-block">
        <span class="history-badge ${q ? classificationClass(q.classification) : ""}">${q ? q.classification : "Pending"}</span>
        <span class="lead-card-score">${q ? q.score + "/100" : "—"}</span>
      </div>
    </div>
    <div class="lead-card-meta">${metaBits || "—"}</div>
    <div class="lead-card-chips">
      <span class="mini-chip ${q?.icp_fit ? "fit" : ""}">ICP: ${q ? (q.icp_fit ? "Strong" : "Not Fit") : "—"}</span>
      <span class="mini-chip">Intent: ${q ? q.buying_intent : "—"}</span>
      <span class="mini-chip">Status: ${escapeHtml(item.status || "New")}</span>
      ${q?.recommended_offer ? `<span class="mini-chip offer-chip">${q.recommended_offer}</span>` : ""}
    </div>
    <div class="lead-card-footer">
      <span>ID: ${item.id}</span>
      <span>Created: ${formatDate(item.created_at)}</span>
      <span>Updated: ${formatDate(item.updated_at)}</span>
      <button class="lead-card-delete" type="button" title="Delete this lead">Delete</button>
    </div>
  `;
  card.addEventListener("click", () => {
    openLeadDrawer(item);
    loadLeadDetails(item.id);
  });
  card.querySelector(".lead-card-delete").addEventListener("click", (e) => {
    e.stopPropagation();
    deleteLead(item.id, item.name);
  });
  return card;
}

async function deleteLead(leadId, leadName) {
  if (!confirm(`Delete "${leadName}" (ID: ${leadId})? This permanently removes it from the database.`)) {
    return;
  }
  try {
    const res = await fetch(`${API_BASE}/leads/${leadId}`, { method: "DELETE" });
    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      throw new Error(errBody.detail || "Unable to delete this lead.");
    }
    loadHistory(); // reload from the database so counts/list reflect the real remaining data
  } catch (err) {
    alert(err.message || "Unable to delete this lead. Please try again.");
  }
}

function scrollToForm() {
  document.getElementById("name").focus({ preventScroll: true });
  form.scrollIntoView({ behavior: "smooth", block: "center" });
}
document.getElementById("addFirstLeadBtn").addEventListener("click", scrollToForm);

function getVisibleLeads(leads) {
  const searchTerm = (document.getElementById("leadSearchInput")?.value || "").trim().toLowerCase();
  return leads.filter((item) => {
    const q = item.qualification;
    const matchesFilter =
      currentLeadFilter === "all" ||
      (currentLeadFilter === "hot" && q?.classification === "HOT") ||
      (currentLeadFilter === "warm" && q?.classification === "WARM") ||
      (currentLeadFilter === "cold" && q?.classification === "COLD");

    if (!matchesFilter) return false;
    if (!searchTerm) return true;

    const haystack = [
      item.name,
      item.company,
      item.job_title,
      item.industry,
      q?.classification,
      q?.score,
      q?.recommended_offer,
      item.country,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    return haystack.includes(searchTerm);
  });
}

async function loadHistory() {
  const listEl = document.getElementById("historyList");
  try {
    const res = await fetch(`${API_BASE}/leads?limit=10`);
    const data = await res.json();
    const leads = data.leads || [];

    updateStats(leads);

    if (leads.length === 0) {
      listEl.innerHTML = `
        <div class="history-empty-state">
          <p>No leads yet</p>
          <p class="history-empty-sub">Add your first lead to begin qualification.</p>
          <button class="btn-primary history-empty-cta" id="addFirstLeadBtn" type="button">Add Your First Lead</button>
        </div>`;
      document.getElementById("addFirstLeadBtn").addEventListener("click", scrollToForm);
      return;
    }

    const visibleLeads = getVisibleLeads(leads);
    listEl.innerHTML = "";
    if (visibleLeads.length === 0) {
      listEl.innerHTML = `
        <div class="history-empty-state">
          <p>No matching leads</p>
          <p class="history-empty-sub">Try another search or switch filters.</p>
        </div>`;
      return;
    }

    visibleLeads.forEach((item) => listEl.appendChild(buildLeadCard(item)));
  } catch (e) {
    listEl.innerHTML = `<p class="history-empty">Unable to load leads. Please try again.</p>`;
  }
}

async function loadLeadDetails(leadId) {
  try {
    const res = await fetch(`${API_BASE}/leads/${leadId}`);
    if (!res.ok) return;
    const data = await res.json();
    if (!data.qualification) return;
    // Reuses the same render path submit() uses, so a lead retrieved later
    // shows the exact same persisted qualification + sales action plan.
    renderResult({ lead: data.lead, qualification: data.qualification }, { cached: false });
    window.scrollTo({ top: resultContent.offsetTop - 24, behavior: "smooth" });
  } catch (e) {
    // silent - history stays interactive even if a single fetch fails
  }
}

async function clearAllLeads() {
  if (!confirm("Delete ALL leads? This permanently wipes every lead from the database and cannot be undone.")) {
    return;
  }
  try {
    const res = await fetch(`${API_BASE}/leads`, { method: "DELETE" });
    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      throw new Error(errBody.detail || "Unable to clear leads.");
    }
    loadHistory(); // reload so the list/stats reflect the now-empty database
  } catch (err) {
    alert(err.message || "Unable to clear leads. Please try again.");
  }
}

async function copyToClipboard(text, successLabel) {
  try {
    await navigator.clipboard.writeText(text);
    if (successLabel) {
      const button = document.activeElement && document.activeElement.tagName === "BUTTON" ? document.activeElement : null;
      if (button) {
        const previous = button.textContent;
        button.textContent = successLabel;
        setTimeout(() => { button.textContent = previous; }, 1200);
      }
    }
  } catch (e) {
    console.warn("Clipboard copy failed:", e);
    alert("Copy failed in this browser. Please copy the text manually.");
  }
}

function bindLeadFilterControls() {
  const filterButtons = document.querySelectorAll(".filter-btn");
  filterButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      currentLeadFilter = btn.dataset.filter || "all";
      filterButtons.forEach((b) => b.classList.toggle("active", b === btn));
      loadHistory();
    });
  });

  const searchInput = document.getElementById("leadSearchInput");
  if (searchInput) {
    searchInput.addEventListener("input", loadHistory);
  }
}

document.getElementById("refreshHistory").addEventListener("click", loadHistory);
document.getElementById("clearAllLeads").addEventListener("click", clearAllLeads);

if (leadDrawerBackdrop) {
  leadDrawerBackdrop.addEventListener("click", closeLeadDrawer);
}
if (drawerCloseBtn) {
  drawerCloseBtn.addEventListener("click", closeLeadDrawer);
}

document.getElementById("copyOfferBtn")?.addEventListener("click", async () => {
  const offer = lastResultData?.qualification?.recommended_offer;
  if (!offer) {
    alert("No offer is available to copy yet.");
    return;
  }
  const text = `${lastResultData.lead.name} (${lastResultData.lead.company}) — Recommended offer: ${offer}`;
  await copyToClipboard(text, "Copied");
});

document.getElementById("copyPlanBtn")?.addEventListener("click", async () => {
  const data = lastResultData;
  if (!data?.qualification) {
    alert("No action plan is available to copy yet.");
    return;
  }
  const text = [
    `${data.lead.name} (${data.lead.company})`,
    `Score: ${data.qualification.score}/100`,
    `Recommended next action: ${data.qualification.next_action}`,
    `Offer: ${data.qualification.recommended_offer}`,
  ].join("\n");
  await copyToClipboard(text, "Copied");
});

bindLeadFilterControls();
checkHealth();
loadHistory();

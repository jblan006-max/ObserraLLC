import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { GitCompare, ShieldAlert, ShieldCheck, FlaskConical, ScrollText, Wrench, Bot, Mail, CalendarClock, Send, Eye, Download, TrendingUp, FileText, BellRing, FileWarning, Sparkles, MessagesSquare, Share2, Volume2, History, Slack, Copy } from "lucide-react";

// Governance Digest Schedule card — digest scheduling, score-drop alerts, weekly SoD evidence
// pack, Slack/Teams Ask, voice briefing & shareable digest. Extracted from SodCommandCenter for
// maintainability; the parent owns all state and passes it (plus handlers) down as props.
export function GovernanceDigestCard(props) {
  const { addScope, approveBusy, approveEvidence, briefingBusy, checkScoreAlert, cooldownRemain, createShare, data, dcfg, dcfgBusy, dcfgLocal, digestBusy, evidBusy, evidPreviewBusy, exportEvidence, muteAlert, muteBusy, openAsk, openEvidPreview, openPreview, playVoice, preview, previewBusy, previewRecap, previewVoice, removeScope, runSlackTest, runTeamsTest, saveDcfg, scoreAlerts, scoreBusy, scoreMute, scorecard, sendDigest, sendEvidence, setDcfgLocal, setScope, sev, shareBriefing, shareBusy, shares, slackAskUrl, slackTest, slackTestBusy, status, teamsAskUrl, teamsTest, teamsTestBusy, testChat, unapproveEvidence, unmuteAlert, voiceBusy, voiceUrl } = props;
  return (
        <div className="bg-card fact-border rounded-xl p-5" data-testid="sod-digest-schedule">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2"><CalendarClock className="w-4 h-4 text-primary" /><h2 className="font-head font-bold text-base">Governance Digest Schedule</h2></div>
            <span data-testid="digest-state" className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${dcfgLocal.enabled ? "bg-low/15 text-low" : "bg-secondary text-muted-foreground"}`}>{dcfgLocal.enabled ? "SCHEDULED" : "PAUSED"}</span>
            <div className="flex-1" />
            <div className="flex items-center gap-2"><span className="text-xs text-muted-foreground">Daily scheduled digest</span><Switch data-testid="digest-enable" checked={dcfgLocal.enabled} onCheckedChange={(v) => setDcfgLocal({ ...dcfgLocal, enabled: v })} /></div>
          </div>
          <p className="text-[11px] text-muted-foreground mt-1">Dispatched by the platform scheduler at <span className="font-mono">{dcfg?.next_window || "08:00 UTC"}</span>. Configure who receives it, on which days, and optionally post a summary to Teams/Slack. {dcfg?.last_at && <>Last sent <span className="font-mono">{new Date(dcfg.last_at).toLocaleString()}</span>.</>}</p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
            <div>
              <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1.5">Send on</div>
              <Select value={dcfgLocal.days} onValueChange={(v) => setDcfgLocal({ ...dcfgLocal, days: v })}><SelectTrigger data-testid="digest-days" className="h-9"><SelectValue /></SelectTrigger>
                <SelectContent><SelectItem value="everyday">Every day</SelectItem><SelectItem value="weekdays">Weekdays only (Mon–Fri)</SelectItem></SelectContent></Select>
            </div>
            <div>
              <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1.5">Recipients (comma-separated · blank = all admins/execs)</div>
              <Textarea data-testid="digest-recipients" rows={2} value={dcfgLocal.recipients} onChange={(e) => setDcfgLocal({ ...dcfgLocal, recipients: e.target.value })} placeholder={(dcfg?.default_recipients || []).join(", ") || "admin@company.com"} />
            </div>
          </div>

          <div className="mt-4 border-t border-border pt-3">
            <div className="flex flex-wrap items-center gap-2 mb-2">
              <Switch data-testid="digest-chat-toggle" checked={dcfgLocal.chat_alert} onCheckedChange={(v) => setDcfgLocal({ ...dcfgLocal, chat_alert: v })} />
              <span className="text-xs">Also post a summary to Slack / Microsoft Teams</span>
              <span className="text-[10px] font-mono text-muted-foreground">{dcfg?.fallback_chat_configured ? "· org webhook available as fallback" : "· no org webhook — add a dedicated one below"}</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div><div className="text-[10px] font-mono uppercase text-muted-foreground mb-1">Dedicated SAP Teams webhook (optional)</div><Input data-testid="digest-teams-url" value={dcfgLocal.teams_url} onChange={(e) => setDcfgLocal({ ...dcfgLocal, teams_url: e.target.value })} placeholder="https://outlook.office.com/webhook/…" /></div>
              <div><div className="text-[10px] font-mono uppercase text-muted-foreground mb-1">Dedicated SAP Slack webhook (optional)</div><Input data-testid="digest-slack-url" value={dcfgLocal.slack_url} onChange={(e) => setDcfgLocal({ ...dcfgLocal, slack_url: e.target.value })} placeholder="https://hooks.slack.com/services/…" /></div>
            </div>
          </div>

          {/* Score-drop alert */}
          <div className="mt-4 border-t border-border pt-3" data-testid="score-alert-config">
            <div className="flex flex-wrap items-center gap-2">
              <BellRing className="w-4 h-4 text-amber" />
              <span className="text-sm font-medium">Governance score-drop alert</span>
              <div className="flex-1" />
              <span className="text-xs text-muted-foreground">Alert Slack/Teams when the score drops below</span>
              <Input type="number" min={0} max={100} data-testid="score-threshold" value={dcfgLocal.score_threshold ?? 60} onChange={(e) => setDcfgLocal({ ...dcfgLocal, score_threshold: e.target.value })} className="w-20 h-8" />
              <Switch data-testid="score-alert-toggle" checked={!!dcfgLocal.score_alert} onCheckedChange={(v) => setDcfgLocal({ ...dcfgLocal, score_alert: v })} />
            </div>
            <div className="flex flex-wrap items-center gap-3 mt-2" data-testid="sev-thresholds">
              <span className="text-xs text-muted-foreground">Also alert when open conflicts exceed —</span>
              <div className="flex items-center gap-1.5"><span className="text-[11px] font-mono text-crit">Critical</span><Input type="number" min={0} data-testid="sev-threshold-Critical" value={dcfgLocal.sev_thresholds?.Critical ?? ""} onChange={(e) => setDcfgLocal({ ...dcfgLocal, sev_thresholds: { ...(dcfgLocal.sev_thresholds || {}), Critical: e.target.value } })} className="w-16 h-8" /></div>
              <div className="flex items-center gap-1.5"><span className="text-[11px] font-mono text-amber">High</span><Input type="number" min={0} data-testid="sev-threshold-High" value={dcfgLocal.sev_thresholds?.High ?? ""} onChange={(e) => setDcfgLocal({ ...dcfgLocal, sev_thresholds: { ...(dcfgLocal.sev_thresholds || {}), High: e.target.value } })} className="w-16 h-8" /></div>
            </div>
            {scoreMute.muted && (
              <div className="mt-2 rounded-md border border-amber/40 bg-amber/[0.08] px-3 py-2 flex flex-wrap items-center gap-2" data-testid="score-mute-banner">
                <BellRing className="w-3.5 h-3.5 text-amber" />
                <span className="text-[11px] text-amber font-medium">Alerts snoozed until {new Date(scoreMute.mute_until).toLocaleString()}</span>
                {scoreMute.mute_reason && <span className="text-[11px] text-muted-foreground">· {scoreMute.mute_reason}</span>}
                <div className="flex-1" />
                <Button size="sm" variant="ghost" className="h-7 text-[11px]" data-testid="score-unmute" onClick={unmuteAlert} disabled={muteBusy}>Un-mute now</Button>
              </div>
            )}
            <div className="flex flex-wrap items-center gap-2 mt-2">
              <span className="text-[11px] text-muted-foreground">Current governance score <b>{scorecard?.current?.governance_score ?? "—"}/100</b>. The daily sweep posts a one-time alert per week while any threshold stays breached.</span>
              <div className="flex-1" />
              {!scoreMute.muted && (
                <>
                  <Button size="sm" variant="ghost" className="h-8 text-[11px]" data-testid="score-mute-24h" onClick={() => muteAlert(24)} disabled={muteBusy}>Snooze 24h</Button>
                  <Button size="sm" variant="ghost" className="h-8 text-[11px]" data-testid="score-mute-7d" onClick={() => muteAlert(168)} disabled={muteBusy}>Snooze 7d</Button>
                </>
              )}
              <Button size="sm" variant="outline" className="h-8 gap-1.5" data-testid="score-alert-check" onClick={checkScoreAlert} disabled={scoreBusy}><BellRing className="w-3.5 h-3.5" />{scoreBusy ? "Checking…" : "Check & alert now"}</Button>
            </div>
            {scoreAlerts.length > 0 && (
              <div className="mt-3 border-t border-border pt-3" data-testid="score-alert-history">
                <div className="text-[10px] font-mono uppercase text-muted-foreground mb-2">Recent alerts · {scoreAlerts.length}</div>
                <div className="space-y-1.5 max-h-[150px] overflow-y-auto pr-1">
                  {scoreAlerts.slice(0, 12).map((a, i) => (
                    <div key={i} data-testid={`score-alert-${i}`} className="flex items-start gap-2 text-[11px]">
                      <span className="font-mono text-muted-foreground w-32 shrink-0">{new Date(a.at).toLocaleString()}</span>
                      <span className="font-head font-bold shrink-0" style={{ color: "hsl(0 84% 60%)" }}>{a.score}/100</span>
                      <span className="text-muted-foreground">{(a.reasons || []).join(" · ")}{a.posted ? "" : " (not posted)"}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Weekly SoD evidence pack */}
          <div className="mt-4 border-t border-border pt-3" data-testid="evidence-export-config">
            <div className="flex flex-wrap items-center gap-2">
              <FileWarning className="w-4 h-4 text-primary" />
              <span className="text-sm font-medium">Weekly SoD evidence pack (auditors)</span>
              <div className="flex-1" />
              <Switch data-testid="evidence-export-toggle" checked={!!dcfgLocal.evidence_export} onCheckedChange={(v) => setDcfgLocal({ ...dcfgLocal, evidence_export: v })} />
            </div>
            <p className="text-[11px] text-muted-foreground mt-1">Auto-email a branded SOX-grade SoD evidence pack PDF — every conflict with its toxic function combination and remediation state — to your auditors on a set weekday.</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-2">
              <div>
                <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1">Send on</div>
                <Select value={dcfgLocal.evidence_day || "mon"} onValueChange={(v) => setDcfgLocal({ ...dcfgLocal, evidence_day: v })}><SelectTrigger data-testid="evidence-day" className="h-9"><SelectValue /></SelectTrigger>
                  <SelectContent>{[["mon", "Monday"], ["tue", "Tuesday"], ["wed", "Wednesday"], ["thu", "Thursday"], ["fri", "Friday"], ["sat", "Saturday"], ["sun", "Sunday"]].map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}</SelectContent></Select>
              </div>
              <div>
                <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1">Auditor recipients (comma-separated · blank = admins/execs)</div>
                <Input data-testid="evidence-recipients" value={dcfgLocal.evidence_recipients || ""} onChange={(e) => setDcfgLocal({ ...dcfgLocal, evidence_recipients: e.target.value })} placeholder="auditor@company.com, soc@company.com" />
              </div>
            </div>
            <div className="mt-3 rounded-md border border-border p-2.5" data-testid="evidence-signoff">
              <div className="text-[10px] font-mono uppercase text-muted-foreground mb-2">Two-step signoff (stamped on the PDF)</div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <div className="text-[10px] text-muted-foreground mb-1">1 · Prepared by</div>
                  <Input data-testid="evidence-prepared-by" value={dcfgLocal.evidence_prepared_by || ""} onChange={(e) => setDcfgLocal({ ...dcfgLocal, evidence_prepared_by: e.target.value })} placeholder="e.g. Sam Prep, GRC Analyst" className="h-8" />
                </div>
                <div>
                  <div className="text-[10px] text-muted-foreground mb-1">2 · Approval</div>
                  {dcfg?.config?.evidence_approved_by ? (
                    <div className="flex items-center gap-2 h-8">
                      <span data-testid="evidence-approval-status" className="text-[11px] px-2 py-0.5 rounded-full font-mono" style={{ background: "hsl(142 70% 45% / 0.14)", color: "hsl(142 70% 34%)" }}>✓ {dcfg.config.evidence_approved_by} · {(dcfg.config.evidence_approved_at || "").slice(0, 10)}</span>
                      <Button size="sm" variant="ghost" className="h-7 text-[11px]" data-testid="evidence-unapprove" onClick={unapproveEvidence} disabled={approveBusy}>Revoke</Button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 h-8">
                      <span data-testid="evidence-approval-status" className="text-[11px] px-2 py-0.5 rounded-full font-mono" style={{ background: "hsl(35 90% 55% / 0.14)", color: "hsl(35 90% 40%)" }}>Pending approval</span>
                      <Button size="sm" variant="outline" className="h-7 text-[11px]" data-testid="evidence-approve" onClick={approveEvidence} disabled={approveBusy}>Approve pack</Button>
                    </div>
                  )}
                </div>
              </div>
              <p className="text-[10px] text-muted-foreground mt-1.5">Save the schedule after editing "Prepared by" (changing it clears any prior approval), then approve. The PDF carries both names + the approval date.</p>
            </div>
            <div className="mt-3" data-testid="auditor-scopes">
              <div className="flex items-center gap-2 mb-1.5">
                <div className="text-[10px] font-mono uppercase text-muted-foreground">Per-auditor scopes — each recipient gets a pack filtered to their areas/systems (blank = full pack)</div>
                <div className="flex-1" />
                <Button size="sm" variant="outline" className="h-7 text-[11px]" data-testid="auditor-scope-add" onClick={addScope}>+ Add scope</Button>
              </div>
              <div className="space-y-2">
                {(dcfgLocal.auditor_scopes || []).map((s, i) => (
                  <div key={i} className="grid grid-cols-1 md:grid-cols-[1.4fr_1fr_1fr_auto] gap-2 items-center" data-testid={`auditor-scope-${i}`}>
                    <Input data-testid={`auditor-scope-email-${i}`} value={s.email} onChange={(e) => setScope(i, "email", e.target.value)} placeholder="auditor@company.com" className="h-8" />
                    <Input data-testid={`auditor-scope-areas-${i}`} value={s.areas} onChange={(e) => setScope(i, "areas", e.target.value)} placeholder="Finance, Treasury" className="h-8" />
                    <Input data-testid={`auditor-scope-systems-${i}`} value={s.systems} onChange={(e) => setScope(i, "systems", e.target.value)} placeholder="S4P, ECP" className="h-8" />
                    <Button size="sm" variant="ghost" className="h-8 text-crit" data-testid={`auditor-scope-remove-${i}`} onClick={() => removeScope(i)}>Remove</Button>
                  </div>
                ))}
                {(!dcfgLocal.auditor_scopes || dcfgLocal.auditor_scopes.length === 0) && <div className="text-[11px] text-muted-foreground">No scopes — every recipient gets the full evidence pack.</div>}
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2 mt-3">
              <Button size="sm" variant="outline" className="h-8 gap-1.5" data-testid="evidence-send-now" onClick={sendEvidence} disabled={evidBusy}><Mail className="w-3.5 h-3.5" />{evidBusy ? "Sending…" : "Send evidence pack now"}</Button>
              <Button size="sm" variant="outline" className="h-8 gap-1.5" data-testid="evidence-preview" onClick={openEvidPreview} disabled={evidPreviewBusy}><Eye className="w-3.5 h-3.5" />{evidPreviewBusy ? "Loading…" : "Preview pack"}</Button>
              <Button size="sm" variant="outline" className="h-8 gap-1.5" data-testid="evidence-export-pdf" onClick={() => exportEvidence("pdf")}><FileText className="w-3.5 h-3.5" /> Download PDF</Button>
              <Button size="sm" variant="outline" className="h-8 gap-1.5" data-testid="evidence-export-csv" onClick={() => exportEvidence("csv")}><Download className="w-3.5 h-3.5" /> Download CSV</Button>
            </div>
          </div>

          <div className="mt-4 border-t border-border pt-3" data-testid="voice-config">
            <div className="flex flex-wrap items-center gap-2">
              <Volume2 className="w-4 h-4 text-primary" />
              <span className="text-sm font-medium">Voice briefing</span>
              <div className="flex-1" />
              <span className="text-[11px] text-muted-foreground">Attach spoken .mp3 to the daily digest email</span>
              <Switch data-testid="voice-attach-toggle" checked={!!dcfgLocal.voice_attach} onCheckedChange={(v) => setDcfgLocal({ ...dcfgLocal, voice_attach: v })} />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-2">
              <div>
                <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1">Narrator voice</div>
                <Select value={dcfgLocal.voice_name || "onyx"} onValueChange={(v) => { setDcfgLocal({ ...dcfgLocal, voice_name: v }); previewVoice(v); }}><SelectTrigger data-testid="voice-name" className="h-9"><SelectValue /></SelectTrigger>
                  <SelectContent>{[["onyx", "Onyx — deep, authoritative"], ["alloy", "Alloy — neutral"], ["nova", "Nova — energetic"], ["shimmer", "Shimmer — bright"], ["echo", "Echo — smooth"]].map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}</SelectContent></Select>
              </div>
              <div>
                <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1">Speed</div>
                <Select value={String(dcfgLocal.voice_speed || 1)} onValueChange={(v) => setDcfgLocal({ ...dcfgLocal, voice_speed: Number(v) })}><SelectTrigger data-testid="voice-speed" className="h-9"><SelectValue /></SelectTrigger>
                  <SelectContent>{[["1", "1× (normal)"], ["1.25", "1.25× (brisk)"], ["1.5", "1.5× (fast)"]].map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}</SelectContent></Select>
              </div>
            </div>
            <div className="mt-2">
              <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1">Spoken intro (optional, ~140 chars — plays first)</div>
              <Input data-testid="voice-intro" maxLength={140} value={dcfgLocal.voice_intro || ""} onChange={(e) => setDcfgLocal({ ...dcfgLocal, voice_intro: e.target.value })} placeholder="e.g. Good morning team, here's this week's access posture." />
            </div>
            <p className="text-[10px] text-muted-foreground mt-1.5">Save the schedule to apply this to the emailed briefing. "Listen to digest" below previews your current selection.</p>
            <div className="mt-3 pt-3 border-t border-border/60 flex flex-wrap items-center gap-2" data-testid="recap-config">
              <History className="w-4 h-4 text-primary" />
              <span className="text-sm font-medium">Weekly AI Q&amp;A recap</span>
              <span className="text-[11px] text-muted-foreground">Email leadership the week's most-asked questions</span>
              <div className="flex-1" />
              {dcfgLocal.recap_enabled && (
                <Select value={dcfgLocal.recap_day || "mon"} onValueChange={(v) => setDcfgLocal({ ...dcfgLocal, recap_day: v })}><SelectTrigger data-testid="recap-day" className="h-8 w-[150px]"><SelectValue /></SelectTrigger>
                  <SelectContent>{[["mon", "Mondays"], ["tue", "Tuesdays"], ["wed", "Wednesdays"], ["thu", "Thursdays"], ["fri", "Fridays"], ["sat", "Saturdays"], ["sun", "Sundays"]].map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}</SelectContent></Select>
              )}
              <Button size="sm" variant="ghost" className="h-8 text-[11px] gap-1" data-testid="recap-preview-btn" onClick={previewRecap}><Eye className="w-3.5 h-3.5" /> Preview</Button>
              <Switch data-testid="recap-toggle" checked={!!dcfgLocal.recap_enabled} onCheckedChange={(v) => setDcfgLocal({ ...dcfgLocal, recap_enabled: v })} />
            </div>
            <div className="mt-3 pt-3 border-t border-border/60" data-testid="brand-config">
              <div className="flex items-center gap-2 mb-2"><Sparkles className="w-4 h-4 text-primary" /><span className="text-sm font-medium">Branding</span><span className="text-[11px] text-muted-foreground">Applied to the digest email &amp; read-only share page</span></div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div>
                  <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1">Logo image URL</div>
                  <Input data-testid="brand-logo" value={dcfgLocal.brand_logo_url || ""} onChange={(e) => setDcfgLocal({ ...dcfgLocal, brand_logo_url: e.target.value })} placeholder="https://…/logo.png" />
                </div>
                <div>
                  <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1">Accent colour (hex)</div>
                  <div className="flex items-center gap-2">
                    <span className="w-9 h-9 rounded-md border border-border shrink-0" data-testid="brand-swatch" style={{ background: (/^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.test(dcfgLocal.brand_accent || "") ? dcfgLocal.brand_accent : "#0f1e3d") }} />
                    <Input data-testid="brand-accent" value={dcfgLocal.brand_accent || ""} onChange={(e) => setDcfgLocal({ ...dcfgLocal, brand_accent: e.target.value })} placeholder="#0f1e3d" />
                  </div>
                </div>
              </div>
            </div>
            <div className="mt-3 pt-3 border-t border-border/60" data-testid="slack-ask-config">
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <Slack className="w-4 h-4 text-primary" />
                <span className="text-sm font-medium">Slack Ask</span>
                <span className="text-[11px] text-muted-foreground">Let leadership ask digest questions from a Slack slash-command</span>
                <div className="flex-1" />
                <Switch data-testid="slack-ask-toggle" checked={!!dcfgLocal.slack_ask} onCheckedChange={(v) => setDcfgLocal({ ...dcfgLocal, slack_ask: v })} />
              </div>
              {dcfgLocal.slack_ask && (
                <div className="space-y-3" data-testid="slack-ask-setup">
                  <div>
                    <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1">Slash-command Request URL (paste into your Slack app)</div>
                    <div className="flex items-center gap-2">
                      <Input data-testid="slack-ask-url" readOnly value={slackAskUrl} className="font-mono text-xs" onFocus={(e) => e.target.select()} />
                      <Button type="button" size="sm" variant="outline" className="gap-1.5 shrink-0" data-testid="slack-ask-copy" onClick={() => { navigator.clipboard?.writeText(slackAskUrl); toast.success("Request URL copied"); }}><Copy className="w-3.5 h-3.5" /> Copy</Button>
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1">Slack app Signing Secret {dcfg?.slack_signing_secret_set && <span className="text-emerald-500 normal-case">· configured</span>}</div>
                    <Input data-testid="slack-ask-secret" type="password" autoComplete="off" value={dcfgLocal.slack_signing_secret || ""} onChange={(e) => setDcfgLocal({ ...dcfgLocal, slack_signing_secret: e.target.value })} placeholder={dcfg?.slack_signing_secret_set ? "•••••••• (leave blank to keep current)" : "Basic Information → App Credentials → Signing Secret"} />
                  </div>
                  <p className="text-[11px] text-muted-foreground leading-relaxed">
                    In your Slack app, create a Slash Command (e.g. <span className="font-mono">/askdigest</span>) pointing at the Request URL above, paste the app's Signing Secret here, then Save. Ask e.g. <span className="font-mono">/askdigest what are the top risks right now?</span> — the AI answers in-channel, grounded in the live SAP access snapshot.
                  </p>
                  <div>
                    <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1.5">One-tap command shortcuts</div>
                    <div className="flex flex-wrap gap-1.5" data-testid="slack-ask-shortcuts">
                      {["top risks", "score trend", "critical", "residual access", "priorities"].map((k) => (
                        <span key={k} className="text-[11px] font-mono px-2 py-0.5 rounded-full bg-secondary/60 border border-border">/askdigest {k}</span>
                      ))}
                    </div>
                    <p className="text-[10px] text-muted-foreground mt-1">Leaders can type just the keyword — it expands to a full grounded question.</p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Button type="button" size="sm" variant="outline" className="gap-1.5" data-testid="slack-ask-test" onClick={runSlackTest} disabled={slackTestBusy}><Send className="w-3.5 h-3.5" />{slackTestBusy ? "Testing…" : "Send a test question"}</Button>
                    <span className="text-[11px] text-muted-foreground">Runs the full round-trip; if a Slack webhook is set, posts the answer to Slack.</span>
                  </div>
                  {slackTest && (
                    <div className="rounded-lg border border-primary/25 bg-primary/[0.04] p-3 text-xs" data-testid="slack-ask-test-result">
                      <div className="font-mono text-[10px] uppercase text-muted-foreground mb-1">Test answer · {slackTest.model}{slackTest.webhook_posted ? " · posted to Slack" : slackTest.webhook_configured ? " · webhook post failed" : " · no Slack webhook set"}</div>
                      <div className="text-foreground/90 leading-relaxed">{slackTest.answer}</div>
                      {!slackTest.signing_secret_set && <div className="text-amber mt-1.5">Save a signing secret above so inbound Slack requests verify.</div>}
                    </div>
                  )}
                </div>
              )}
            </div>
            <div className="mt-3 pt-3 border-t border-border/60" data-testid="teams-ask-config">
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <MessagesSquare className="w-4 h-4 text-primary" />
                <span className="text-sm font-medium">Teams Ask</span>
                <span className="text-[11px] text-muted-foreground">Ask the digest from Microsoft Teams via an Outgoing Webhook</span>
                <div className="flex-1" />
                <Switch data-testid="teams-ask-toggle" checked={!!dcfgLocal.teams_ask} onCheckedChange={(v) => setDcfgLocal({ ...dcfgLocal, teams_ask: v })} />
              </div>
              {dcfgLocal.teams_ask && (
                <div className="space-y-3" data-testid="teams-ask-setup">
                  <div>
                    <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1">Outgoing-webhook callback URL (paste into Teams)</div>
                    <div className="flex items-center gap-2">
                      <Input data-testid="teams-ask-url" readOnly value={teamsAskUrl} className="font-mono text-xs" onFocus={(e) => e.target.select()} />
                      <Button type="button" size="sm" variant="outline" className="gap-1.5 shrink-0" data-testid="teams-ask-copy" onClick={() => { navigator.clipboard?.writeText(teamsAskUrl); toast.success("Callback URL copied"); }}><Copy className="w-3.5 h-3.5" /> Copy</Button>
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] font-mono uppercase text-muted-foreground mb-1">Teams outgoing-webhook HMAC secret {dcfg?.teams_ask_secret_set && <span className="text-emerald-500 normal-case">· configured</span>}</div>
                    <Input data-testid="teams-ask-secret" type="password" autoComplete="off" value={dcfgLocal.teams_ask_secret || ""} onChange={(e) => setDcfgLocal({ ...dcfgLocal, teams_ask_secret: e.target.value })} placeholder={dcfg?.teams_ask_secret_set ? "•••••••• (leave blank to keep current)" : "Teams → Manage team → Apps → Create an Outgoing Webhook → copy the security token"} />
                  </div>
                  <p className="text-[11px] text-muted-foreground leading-relaxed">
                    In Teams, create an Outgoing Webhook pointing at the callback URL above, paste the security token here, then Save. @mention the webhook with a question (e.g. <span className="font-mono">@Governance top risks</span>) — the AI replies in the channel, grounded in the live SAP access snapshot.
                  </p>
                  <div className="flex flex-wrap items-center gap-2">
                    <Button type="button" size="sm" variant="outline" className="gap-1.5" data-testid="teams-ask-test" onClick={runTeamsTest} disabled={teamsTestBusy}><Send className="w-3.5 h-3.5" />{teamsTestBusy ? "Testing…" : "Send a test question"}</Button>
                    <span className="text-[11px] text-muted-foreground">Runs the full round-trip; if a Teams webhook is set, posts the answer to Teams.</span>
                  </div>
                  {teamsTest && (
                    <div className="rounded-lg border border-primary/25 bg-primary/[0.04] p-3 text-xs" data-testid="teams-ask-test-result">
                      <div className="font-mono text-[10px] uppercase text-muted-foreground mb-1">Test answer · {teamsTest.model}{teamsTest.webhook_posted ? " · posted to Teams" : teamsTest.webhook_configured ? " · webhook post failed" : " · no Teams webhook set"}</div>
                      <div className="text-foreground/90 leading-relaxed">{teamsTest.answer}</div>
                      {!teamsTest.secret_set && <div className="text-amber mt-1.5">Save an HMAC secret above so inbound Teams requests verify.</div>}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2 mt-4">
            <Button size="sm" data-testid="digest-save" onClick={saveDcfg} disabled={dcfgBusy}>{dcfgBusy ? "Saving…" : "Save schedule"}</Button>
            <Button size="sm" variant="outline" className="gap-1.5" data-testid="digest-preview" onClick={openPreview} disabled={previewBusy}><Eye className="w-3.5 h-3.5" />{previewBusy ? "Loading…" : "Preview email"}</Button>
            <Button size="sm" variant="outline" className="gap-1.5" data-testid="digest-test-chat" onClick={testChat}><Send className="w-3.5 h-3.5" /> Test chat alert</Button>
            <Button size="sm" variant="outline" className="gap-1.5 border-primary/40 text-primary hover:bg-primary/[0.06]" data-testid="digest-ask-open" onClick={openAsk}><MessagesSquare className="w-3.5 h-3.5" /> Ask AI about this digest</Button>
            <Button size="sm" variant="outline" className="gap-1.5" data-testid="digest-share" onClick={createShare} disabled={shareBusy}><Share2 className="w-3.5 h-3.5" />{shareBusy ? "Creating…" : "Copy share link"}</Button>
            <Button size="sm" variant="outline" className="gap-1.5" data-testid="digest-voice" onClick={playVoice} disabled={voiceBusy}><Volume2 className="w-3.5 h-3.5" />{voiceBusy ? "Generating…" : "Listen to digest"}</Button>
            <Button size="sm" variant="outline" className="gap-1.5" data-testid="digest-share-briefing" onClick={shareBriefing} disabled={briefingBusy}><Send className="w-3.5 h-3.5" />{briefingBusy ? "Sending…" : "Share briefing"}</Button>
            <Button size="sm" variant="outline" className="gap-1.5" data-testid="digest-send-now" onClick={sendDigest} disabled={digestBusy || cooldownRemain > 0}><Mail className="w-3.5 h-3.5" />{digestBusy ? "Sending…" : cooldownRemain > 0 ? `Send again in ${cooldownRemain}s` : "Send digest now"}</Button>
          </div>
          {voiceUrl && (
            <div className="mt-3 flex flex-wrap items-center gap-3 rounded-lg border border-primary/25 bg-primary/[0.04] p-3" data-testid="digest-voice-player">
              <Volume2 className="w-4 h-4 text-primary shrink-0" />
              <audio controls src={voiceUrl} className="h-9 flex-1 min-w-[220px]" data-testid="digest-voice-audio" />
              <a href={voiceUrl} download="sap-governance-digest.mp3" data-testid="digest-voice-download" className="text-[11px] text-primary hover:underline">Download .mp3</a>
            </div>
          )}
          {shares && shares.total > 0 && (
            <div className="mt-4 border-t border-border pt-3" data-testid="digest-shares">
              <div className="flex items-center gap-2 mb-2">
                <Share2 className="w-4 h-4 text-primary" />
                <span className="text-sm font-medium">Read-only share links</span>
                <span className="text-[11px] text-muted-foreground" data-testid="digest-shares-summary">· {shares.total} link(s) · {shares.total_opens} total open(s)</span>
              </div>
              <div className="space-y-1.5 max-h-[160px] overflow-y-auto pr-1">
                {shares.shares.map((s, i) => (
                  <div key={s.token} data-testid={`digest-share-row-${i}`} className="flex flex-wrap items-center gap-2 text-[11px]">
                    <span className={`px-1.5 py-0.5 rounded-full font-mono ${s.expired ? "bg-secondary text-muted-foreground" : "bg-primary/15 text-primary"}`}>{s.expired ? "expired" : "active"}</span>
                    <span className="font-mono text-muted-foreground">…{s.token.slice(-6)}</span>
                    <span className="font-bold" data-testid={`digest-share-opens-${i}`}>{s.opens} open{s.opens === 1 ? "" : "s"}</span>
                    <span className="text-muted-foreground">{s.last_opened_at ? `· last ${new Date(s.last_opened_at).toLocaleString()}` : "· not opened yet"}</span>
                    <div className="flex-1" />
                    {Array.isArray(s.series) && s.series.some((n) => n > 0) && (
                      <svg width="70" height="18" viewBox="0 0 70 18" data-testid={`digest-share-spark-${i}`} className="opacity-80">
                        {(() => { const mx = Math.max(...s.series, 1); const w = 70 / s.series.length; return s.series.map((n, j) => (
                          <rect key={j} x={j * w + 0.5} y={18 - Math.max(2, (n / mx) * 16)} width={Math.max(1, w - 1)} height={Math.max(2, (n / mx) * 16)} rx="0.5" fill="hsl(199 89% 48%)" />
                        )); })()}
                      </svg>
                    )}
                    <button data-testid={`digest-share-copy-${i}`} onClick={() => { navigator.clipboard?.writeText(s.url); toast.success("Link copied"); }} className="text-primary hover:underline">Copy</button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
  );
}

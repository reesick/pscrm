+-----------------------------------------------------------------------+
| **PRODUCT REQUIREMENTS DOCUMENT**                                     |
|                                                                       |
| **PS-CRM**                                                            |
|                                                                       |
| Smart Public Service CRM                                              |
|                                                                       |
| Civic Intelligence Layer for Delhi MCD                                |
|                                                                       |
| Team BlackHaze · Vishwakarma Institute of Technology                  |
|                                                                       |
| Version 1.0 · 2025                                                    |
+-----------------------------------------------------------------------+

+-------------+-------------+-------------+-------------+-------------+
| **FastAPI** | **Next.js** | *           | **          | **Gemini    |
|             |             | *Supabase** | LangGraph** | 2.5**       |
| Backend     | Frontend    |             |             |             |
|             |             | Database    | Agents      | LLM         |
+-------------+-------------+-------------+-------------+-------------+

+-----------------------------------------------------------------------+
| **01**                                                                |
|                                                                       |
| **Product Overview**                                                  |
|                                                                       |
| What PS-CRM is and why it exists                                      |
+-----------------------------------------------------------------------+

**1.1 What Is PS-CRM**

PS-CRM (Public Service CRM) is an AI-driven civic intelligence platform
that operates as an intelligence layer on top of India\'s existing
government grievance systems --- primarily CPGRAMS at the national level
and Delhi Mitra at the city level. It does not replace these systems. It
makes them smarter.

The core idea is simple: today, when a citizen files a complaint, it
becomes a ticket. A ticket has a status --- pending, in progress,
closed. Nothing more. There is no understanding of what infrastructure
is failing, which areas keep reporting the same problems, or whether the
contractor who was assigned to fix a drain actually fixed it.

PS-CRM treats every complaint as a signal. A signal about a specific
physical asset --- a streetlight, a drain, a road segment, a tree. These
signals are processed by a network of AI agents that classify them,
route them to the right department, monitor SLA deadlines, follow up
with contractors and citizens, and aggregate patterns into predictive
analytics that allow administrators to act before failures escalate.

**1.2 The Transformation**

  -----------------------------------------------------------------------
  **Traditional System**              **PS-CRM**
  ----------------------------------- -----------------------------------
  Citizen selects department manually System auto-identifies responsible
                                      department(s)

  Complaint linked to a ward name     Complaint linked to a specific
                                      asset ID and GPS coordinate

  Officer manually checks pending     Agents auto-remind, escalate, and
  tasks                               follow up

  Citizens see: Pending / Closed      Citizens see: live status,
                                      timeline, officer name, ETA

  Complaints expire with no insight   Complaints feed predictive hotspot
                                      detection

  Contractor performance invisible    Contractor scorecard built
                                      automatically over time
  -----------------------------------------------------------------------

**1.3 Scope of This Document**

This PRD covers the complete PS-CRM platform: all user-facing features,
system behaviour, agent logic, data architecture, API contracts, UI
design principles, the development phasing plan, and verification
criteria for each phase. It is written for a development team of 4--5
people building toward a hackathon demo and subsequent production
readiness.

+-----------------------------------------------------------------------+
| **02**                                                                |
|                                                                       |
| **Problem Statement**                                                 |
|                                                                       |
| Why existing systems fall short                                       |
+-----------------------------------------------------------------------+

**2.1 The Current State of Civic Grievance Systems**

India processes approximately 2 crore grievances per year through
CPGRAMS alone. Delhi, as the national capital, generates thousands of
civic complaints monthly across categories including roads, drainage,
streetlights, garbage, trees, and water supply. Delhi Mitra --- launched
in 2026 --- was a significant step forward. It unified complaint
channels, introduced a 3-tier escalation hierarchy (JSSA → AA → FAA),
enforced 41-day SLAs, and mandated 100% citizen feedback collection.

Despite these improvements, both CPGRAMS and Delhi Mitra remain
fundamentally reactive, compliance-driven ticket trackers. They ensure
complaints are processed within bureaucratic timelines. They do not make
governance smarter.

**2.2 Structural Gaps**

**Gap 1 --- Department Guesswork**

Citizens are required to select the responsible department when filing a
complaint. This assumes civic knowledge most people do not have. A tree
whose roots are breaking a footpath and simultaneously touching an
electricity pole involves at minimum three departments: Forest
Department, Electricity Department, and Public Works Department. A
citizen has no reliable way to know this. The result is that 35--45% of
complaints are initially misrouted, creating delays and duplicate
filings.

**Gap 2 --- Complaints Exist as Text, Not as Infrastructure Signals**

When a complaint is filed saying \'pothole on main road near the
market,\' the system records this as a text string tied to a ward name.
There is no connection to a specific road segment ID, no awareness of
whether that segment has been complained about 14 times in the last 3
months, and no way for a maintenance team to know exactly where to go
without calling the citizen back. Asset-level context is entirely
missing.

**Gap 3 --- No Predictive or Pattern Intelligence**

Complaints are handled in isolation. There is no mechanism to detect
that Sector 5 receives 20+ drainage complaints every pre-monsoon season,
or that a specific stretch of road has been patched three times in two
years and still keeps failing. Each complaint is treated as a new event
with no memory. This makes governance entirely reactive --- authorities
respond only after failures become visible, not before.

**Gap 4 --- Contractor Accountability Gap**

Once a complaint is marked closed by a JSSA officer, the system does not
verify whether work was actually done, done correctly, or done by a
qualified contractor. Contractor performance --- delays, citizen
rejections, work that needs to be redone --- is invisible to
procurement. Poor contractors continue to be hired because there is no
empirical record of their failure rate.

**Gap 5 --- Transparency Deficit**

Citizens can check whether their complaint is open or closed. Nothing
more. They cannot see who is responsible, when work is scheduled to
begin, what progress has been made, or whether their area has a pattern
of recurring failures. This opacity breeds distrust and discourages
future reporting.

  -----------------------------------------------------------------------
  **Gap**                               **Metric Impact**
  ------------------------------------- ---------------------------------
  Complaint misrouting                  35--45% of complaints initially
                                        misdirected

  Recurring unresolved issues           30--40% of infrastructure
                                        failures are recurring

  Predictive analytics gap              20--35% efficiency gain possible
                                        with analytics

  Resolution time                       30--50% reduction achievable with
                                        automation

  Citizen trust                         25--40% satisfaction improvement
                                        with transparency
  -----------------------------------------------------------------------

+-----------------------------------------------------------------------+
| **03**                                                                |
|                                                                       |
| **User Roles & Personas**                                             |
|                                                                       |
| Who uses PS-CRM and what they need                                    |
+-----------------------------------------------------------------------+

**3.1 Role Overview**

PS-CRM serves six distinct user types. Each has a different level of
system access, a different primary task, and a different dashboard
experience. Role-based access control is enforced at the API level ---
every endpoint checks the user\'s role before returning data. No role
can access data outside their scope.

  ------------------------------------------------------------------------
  **Role**      **Who They Are**   **Primary Goal**    **Access Scope**
  ------------- ------------------ ------------------- -------------------
  Citizen       Any resident of    Submit complaint,   Public --- no login
                Delhi filing a     track resolution    required for
                complaint                              tracking

  JSSA          Junior field       Resolve assigned    Their ward only
                officer assigned   complaints within   
                to a ward          SLA                 

  AA            Area Admin ---     Handle escalated    Their zone
                second-level       cases, audit JSSAs  (multiple wards)
                escalation                             
                authority                              

  FAA           Final Authority    Final escalation,   Full department
                Admin ---          tender approval     scope
                city-level                             

  Super Admin   Department head or Analytics,          Full system access
                system             contractor          
                administrator      management, system  
                                   config              

  Contractor    External vendor    Update task         Only their assigned
                assigned to work   progress, upload    tasks
                orders             proof               
  ------------------------------------------------------------------------

**3.2 User Journeys**

**Citizen Journey**

A citizen notices a broken streetlight outside their house. They open
Telegram, type a message to the PS-CRM bot describing the issue, and
share their location. The bot responds with a grievance ID and tells
them which department has been notified. Over the next few days they
receive Telegram messages as the status changes. When the JSSA marks the
work done, they receive a final message asking them to confirm the fix.
They reply \'yes\' and the complaint closes. If the light is still
broken, they reply \'no\' and the complaint automatically reopens and
escalates.

**JSSA Officer Journey**

A JSSA officer starts their day by opening the admin dashboard. They see
a map of their ward with color-coded pins --- red for urgent, orange for
approaching SLA, green for in-progress. They click a red pin, read the
complaint detail, see the exact asset location on the map, and assign it
to a field technician. They receive a notification when the technician
uploads a mid-job proof photo. When work is complete and the citizen
confirms, the complaint closes automatically.

**Super Admin Journey**

A Super Admin reviews the morning dashboard. A predictive hotspot alert
shows that Ward 14 has had 11 drainage complaints in the past 3 weeks,
clustered within 300 meters. They initiate a proactive maintenance order
before the ward reaches complaint saturation. They also review the
contractor scorecard and see that one contractor has a 43% citizen
rejection rate --- they flag this contractor for review before the next
tender cycle.

+-----------------------------------------------------------------------+
| **04**                                                                |
|                                                                       |
| **Feature Breakdown**                                                 |
|                                                                       |
| What each role can see and do                                         |
+-----------------------------------------------------------------------+

**4.1 Citizen Features**

**Complaint Submission**

Citizens can file complaints through three channels: the Telegram bot,
the public web portal, or a call centre. All three channels feed into
the same intake pipeline --- there is no functional difference in how
complaints from each channel are processed.

On first submission, the citizen\'s phone number is verified via OTP.
This prevents spam and allows the system to send status notifications to
the right person. After verification, the citizen\'s phone is stored in
hashed form --- it is never exposed in any dashboard or API response.

The submission form (or bot conversation) collects: a description of the
issue in any language, the location (auto-detected via GPS or manually
pinned on map), and optional photos. Voice notes can also be submitted
via the Telegram bot. The system accepts input in Hindi, English, and 5
other Indian languages via Bhashini API translation.

**Complaint Tracking**

Every complaint receives a unique grievance ID. This ID is also synced
with Delhi Mitra so the complaint exists in both systems. Citizens can
paste their grievance ID into the public portal search bar --- no login
required --- and see the current status, the department it has been
assigned to, the officer\'s name (not contact details), and a timeline
of every status update.

**Notifications via Telegram**

Every significant status change triggers a Telegram message to the
citizen. Notifications are sent when: the complaint is classified and
assigned, when work begins, when the SLA is approaching, when work is
marked complete, and when the complaint is closed. The final
notification asks the citizen to confirm resolution.

**Resolution Confirmation**

Citizen confirmation is a mandatory step before permanent closure. The
Survey Agent sends a Telegram message asking the citizen to confirm the
fix. If they approve, the complaint closes and the contractor\'s profile
is updated positively. If they reject, the complaint reopens
automatically and escalates to the AA level. If there is no response
within 72 hours, the complaint auto-closes with a flag indicating
citizen was unresponsive --- it remains visible on the public dashboard
as unverified.

**4.2 JSSA Officer Features**

**Ward Map Dashboard**

The JSSA\'s primary view is a map of their ward with all complaints
plotted as pins. Each pin has an icon representing the complaint
category (drainage, streetlight, road, tree, etc.) and a color
representing urgency and SLA status. A sidebar shows the same complaints
as a list, sortable by urgency, date, and SLA deadline. Officers can
switch between map and list view depending on preference.

Clicking a complaint pin opens a detail panel without leaving the map.
The panel shows: the full complaint description, any attached photos,
the specific asset ID it is linked to (with a direct map marker on the
exact asset), the citizen\'s original language text and translated
version, the full status timeline, and action buttons.

**Task Actions**

From the detail panel, the JSSA can accept a complaint (confirming they
have taken ownership), update the status, assign it to a specific field
technician, add internal notes (not visible to citizens), and upload
proof photos at mid-job and final stages. Status transitions are
governed by the state machine --- the JSSA cannot skip states or mark
something closed without following the required proof upload steps.

**SLA Visibility**

Each complaint shows a clear SLA countdown --- how many hours remain
before the deadline. Complaints approaching their SLA are highlighted
and sorted to the top of the list. The Follow-Up Agent handles automated
reminders, but officers can also see the urgency directly in their
dashboard without waiting for a notification.

**4.3 AA / FAA Features**

**Escalation Queue**

The AA sees all complaints that have been escalated from the JSSA level
in their zone. Each escalated complaint shows why it was escalated ---
SLA breach, citizen rejection, or manual escalation --- along with the
history of what the JSSA attempted. The AA can reassign the complaint to
a different JSSA, initiate a tender process for large-scope work, or
resolve it directly.

**Officer Performance View**

The AA has access to a performance table for all JSSAs under their zone.
This shows total complaints assigned, total resolved, escalation count,
average resolution time, and reopen rate. This view is read-only --- it
surfaces data, it does not allow the AA to modify officer records.

**Tender Initiation**

For complaints that require contracted work rather than in-house
resolution, the FAA can initiate a tender from the complaint detail
view. This creates a work order record in the system, links it to the
complaint, and notifies the Super Admin for approval. Once a contractor
is assigned to the tender, the Contractor Agent begins tracking their
progress.

**4.4 Super Admin Features**

**Analytics Dashboard**

The Super Admin\'s home view is a metrics dashboard. The top row shows
four KPI cards: total active complaints, average resolution time this
month, SLA compliance percentage, and number of active hotspot alerts.
Below this is a time-series chart of complaint volume by category, and a
map showing open complaints across all wards with a heatmap intensity
overlay for complaint density.

**Predictive Hotspot Map**

A dedicated map view shows all currently detected infrastructure
hotspots generated by the nightly Predictive Agent. Each hotspot is
shown as a circle on the map with a severity color (low, medium, high)
and a label showing the category and complaint count. Clicking a hotspot
shows the list of complaints that form the cluster and a suggested
maintenance action. The Super Admin can convert a hotspot into a
proactive maintenance order directly from this view.

**Contractor Scorecards**

A table lists all registered contractors with computed performance
metrics: tasks assigned, tasks completed on time, citizen rejection
rate, reopen rate, and an overall reliability score derived from these
metrics. Contractors below a configurable threshold are flagged. The
Super Admin can deactivate a contractor, preventing them from being
assigned new work orders until reviewed.

**System Configuration**

The configuration panel allows the Super Admin to manage: the department
→ JSSA → ward mapping table (which officer is responsible for which
ward), SLA thresholds per complaint category (drainage SLA may differ
from streetlight SLA), geo-fence radius for citizen notifications, and
confidence threshold for LLM routing (if Gemini confidence falls below
this, the complaint is queued for human review instead of
auto-assigned).

**4.5 Contractor Features**

**Task Portal**

Contractors access a minimal portal showing only their assigned work
orders. Each work order shows: the complaint description, the exact
location on a map, the linked asset ID, the deadline, and the current
status. Contractors are required to upload a mid-job proof photo before
the system allows them to mark a task as In Progress, and a final proof
photo before they can mark it as Work Done. These uploads are stored in
Supabase Storage and linked to the complaint record.

**Performance History**

Contractors can view their own scorecard --- tasks completed, citizen
approval rate, and any flagged rejections. This gives them visibility
into how their performance is being tracked and creates accountability
without requiring a separate meeting or audit.

+-----------------------------------------------------------------------+
| **05**                                                                |
|                                                                       |
| **Agent Logic & Interaction Flows**                                   |
|                                                                       |
| How the AI agents think and coordinate                                |
+-----------------------------------------------------------------------+

**5.1 Why Agents**

A traditional backend handles requests and returns responses. Agents are
different --- they are persistent, event-driven processes that react to
state changes and take autonomous actions. In PS-CRM, agents replace
what would otherwise be manual administrative work: sending follow-up
messages, checking SLA deadlines, requesting photos, running nightly
analytics. Each agent has a single, well-defined responsibility. They do
not overlap. The Supervisor Agent is the only one that coordinates
across all others.

All agents are built using LangGraph, an open-source framework for
stateful, event-driven agent workflows. LangGraph allows each agent to
maintain state between executions, supports human-in-the-loop
checkpoints where a human must approve before the agent proceeds, and
provides streaming outputs so administrators can see what agents are
doing in near real-time on the dashboard.

**5.2 Agent Roster**

  ------------------------------------------------------------------------
  **Agent**        **Trigger**        **Responsibility**
  ---------------- ------------------ ------------------------------------
  Supervisor Agent New complaint      Orchestrates the full complaint
                   created            lifecycle. Calls other agents in
                                      sequence. The entry point for all
                                      agent activity.

  Classification   Called by          Extracts complaint category, urgency
  Agent            Supervisor on new  score (1--5), affected asset types,
                   complaint          and responsible departments using
                                      rule engine + Gemini.

  GeoSpatial Agent Called by          Takes GPS coordinates, queries
                   Supervisor after   PostGIS to find the nearest matching
                   classification     infrastructure asset, returns asset
                                      ID and ward.

  Department       Called after       Determines one or more responsible
  Routing Agent    GeoSpatial         departments. Creates one sub-task
                   completes          per department for multi-department
                                      issues.

  Follow-Up Agent  Subscribes to all  Monitors SLA clocks. Sends reminders
                   ASSIGNED and       at 50% and 90% of SLA window.
                   IN_PROGRESS        Auto-escalates at 100%.
                   complaints         

  Survey Agent     Triggered when     Sends mid-resolution and
                   JSSA marks Work    final-resolution messages to citizen
                   Done               via Telegram. Parses response and
                                      updates complaint status.

  Contractor Agent Triggered when a   Monitors proof photo submission.
                   work order is      Blocks status transitions if proof
                   assigned to a      is missing. Escalates if no proof
                   contractor         after 24 hours.

  Predictive Agent Render Cron Job    Queries complaint history, runs
                   --- runs nightly   DBSCAN spatial clustering, detects
                   at 2am             emerging hotspots, pushes alerts to
                                      Super Admin dashboard.
  ------------------------------------------------------------------------

**5.3 Complaint Lifecycle State Machine**

Every complaint in the system follows a strict state machine. States can
only transition forward via authenticated agent events or verified user
actions. No manual status overrides are permitted --- every transition
is logged with a timestamp, actor identity, and reason. This creates a
complete, tamper-proof audit trail for every complaint.

  -----------------------------------------------------------------------
  State Flow: NEW → CLASSIFIED → ASSIGNED → IN_PROGRESS →
  MID_SURVEY_PENDING → FINAL_SURVEY_PENDING → CLOSED Side states (can
  occur from multiple points): ESCALATED, REOPENED Terminal states:
  CLOSED, CLOSED_UNVERIFIED (no citizen response after 72 hours)

  -----------------------------------------------------------------------

  -------------------------------------------------------------------------
  **Transition**         **Trigger**        **Who / What Causes It**
  ---------------------- ------------------ -------------------------------
  NEW → CLASSIFIED       Automatic          Classification Agent completes
                                            category + department
                                            identification

  CLASSIFIED → ASSIGNED  Automatic          Department Routing Agent
                                            assigns to JSSA queue, JSSA
                                            accepts complaint

  ASSIGNED → IN_PROGRESS JSSA action        JSSA updates status after field
                                            team is dispatched. Requires
                                            mid-job proof photo.

  IN_PROGRESS →          Automatic          Survey Agent sends
  MID_SURVEY_PENDING                        mid-resolution message to
                                            citizen

  MID_SURVEY_PENDING →   JSSA action        JSSA marks Work Done. Requires
  FINAL_SURVEY_PENDING                      final proof photo uploaded.

  FINAL_SURVEY_PENDING → Citizen action     Citizen confirms resolution via
  CLOSED                                    Telegram

  FINAL_SURVEY_PENDING → Citizen action     Citizen rejects resolution.
  REOPENED                                  Escalates to AA.

  FINAL_SURVEY_PENDING → Automatic (72h     No citizen response after 72
  CLOSED_UNVERIFIED      timeout)           hours. Survey Agent
                                            auto-closes.

  ANY → ESCALATED        Follow-Up Agent    SLA breach detected at 100% of
                                            SLA window
  -------------------------------------------------------------------------

**5.4 Classification Logic --- How the AI Decides**

The classification pipeline is a hybrid of deterministic rules and LLM
reasoning. The two approaches are not equal --- the rule engine runs
first, and the LLM is only invoked when the rule engine cannot resolve
the complaint with sufficient confidence. This keeps costs low, latency
fast for simple cases, and accuracy high for ambiguous ones.

**Step 1 --- Rule Engine**

The complaint text (translated to English) is passed through a keyword
dictionary. This dictionary maps known civic terms to categories and
departments. For example: \'drain\', \'sewer\', \'waterlogging\' maps to
Drainage → Public Works Department. \'streetlight\', \'lamp post\',
\'electric pole\' maps to Electricity → BSES/TPDDL. The dictionary is
maintained as a configuration file and can be updated without code
changes.

If the keyword match returns a single category and a single department
with high confidence (defined as 85% or above based on keyword density
and match quality), the classification is finalised directly. No LLM
call is made.

**Step 2 --- Gemini 2.5 Flash (Ambiguous Cases)**

If confidence is below 85% --- because the complaint is in unusual
phrasing, involves multiple issues, or uses terminology not in the
dictionary --- the translated complaint text is sent to Gemini 2.5 Flash
via the Google AI API. The prompt instructs Gemini to return a
structured response containing: the primary complaint category, an
urgency score from 1 to 5, the list of affected asset types, and the
list of responsible departments.

Gemini\'s response is not trusted blindly. It is passed back through the
rule engine for validation. The rule engine checks that the departments
Gemini identified are valid departments in the system, that the asset
types are known asset types in the registry, and that the combination
makes logical sense. If validation fails, the complaint is queued for
human review rather than auto-assigned.

**Step 3 --- Multi-Department Splitting**

If classification results in more than one responsible department, the
complaint is split into sub-tasks --- one per department. Each sub-task
has its own SLA clock, its own JSSA assignment, and its own status. The
parent complaint is not considered closed until all sub-tasks are
closed. Citizens see a unified status for the parent complaint, but
internal dashboards show the per-department breakdown.

**5.5 GeoSpatial Resolution Logic**

Once classification is complete, the GeoSpatial Agent receives the GPS
coordinates from the complaint submission. It performs two PostGIS
queries in sequence.

The first query finds all infrastructure assets of the identified asset
type within a 50-metre radius of the complaint coordinates. If multiple
assets are found, the nearest one is selected. The asset\'s ID, type,
department, and ward are attached to the complaint record.

The second query performs a spatial containment check: it finds which
ward boundary polygon contains the complaint\'s coordinates. This
determines the JSSA responsible for that ward. The ward ID and JSSA ID
are recorded on the complaint.

If no asset is found within 50 metres --- which can happen for
complaints about new issues or in areas where the asset registry is
incomplete --- the complaint is still processed but marked with an
\'asset unlinked\' flag. It is still assigned to the correct ward and
department based on coordinates alone.

**5.6 Follow-Up and Escalation Logic**

The Follow-Up Agent runs continuously as a background process. It does
not poll the database on a timer --- it subscribes to Supabase Realtime
and receives an event every time a complaint\'s status changes to
ASSIGNED or IN_PROGRESS. It then registers the complaint\'s SLA deadline
in an internal schedule.

At 50% of the SLA window remaining, the agent sends a Telegram
notification to the assigned JSSA: a reminder that the complaint is
active and the deadline is approaching. No escalation occurs at this
stage --- it is informational only.

At 90% of the SLA window remaining, the agent sends a warning to the
JSSA and also notifies the AA. The AA is alerted that a complaint in
their zone is at risk of breaching SLA.

At 100% --- the SLA deadline has passed --- the complaint is
automatically escalated. Its status gains the ESCALATED flag, a
complaint event is logged, the JSSA\'s escalation count is incremented
on their officer profile, and the AA receives a direct escalation
notification. The AA now has 10 days to resolve before it escalates
further to the FAA.

**5.7 Predictive Analytics Logic**

The Predictive Agent runs as a nightly scheduled job via Render Cron
Jobs at 2:00 AM. It queries the complaint history from Supabase for the
past 90 days, grouping complaints by category and geographic proximity.

The clustering algorithm used is DBSCAN (Density-Based Spatial
Clustering of Applications with Noise). DBSCAN is well-suited for
geographic complaint data because it does not require a pre-defined
number of clusters, it naturally handles areas with no clusters (sparse
complaints are treated as noise), and it can detect clusters of
arbitrary shape --- important for road corridors and drainage channels
that are long and narrow rather than circular.

A cluster is flagged as a hotspot when it contains 5 or more complaints
of the same category within a 200-metre radius within a 30-day window.
The severity score (1--5) is computed from the cluster density and the
average urgency of the complaints within it.

Each detected hotspot is written to the hotspots table in Supabase.
Supabase Realtime pushes this update to any open Super Admin dashboard
sessions, so hotspots appear without requiring a page refresh. Hotspots
remain active until a Super Admin manually resolves them or until the
complaint count in that cluster drops below the threshold in the
following night\'s run.

+-----------------------------------------------------------------------+
| **06**                                                                |
|                                                                       |
| **System Architecture**                                               |
|                                                                       |
| How all components connect                                            |
+-----------------------------------------------------------------------+

**6.1 Architecture Philosophy**

PS-CRM is built on three principles: simplicity over cleverness,
event-driven over polling, and Supabase as the single source of truth.
Every component reads from and writes to Supabase. No component
communicates directly with another component --- they communicate
through database state changes that are broadcast via Supabase Realtime.
This makes the system easy to debug, easy to extend, and resilient to
individual component failures.

**6.2 Component Map**

  ------------------------------------------------------------------------
  **Layer**       **Component**   **Technology**   **Responsibility**
  --------------- --------------- ---------------- -----------------------
  Citizen         Telegram Bot    Telegram Bot     Receive complaints,
  Channels                        API + Python     send status updates,
                                                   run surveys

  Citizen         Web Portal      Next.js (public  Complaint submission
  Channels                        routes)          form, status lookup,
                                                   public map

  Intake          FastAPI Backend FastAPI on       API gateway, OTP
                                  Render           verification,
                                                   translation, file
                                                   uploads, agent
                                                   orchestration entry
                                                   point

  Intelligence    Agent Layer     LangGraph        Classification,
                                  (Python)         routing, follow-up,
                                                   surveys, contractor
                                                   tracking, predictive
                                                   analytics

  Intelligence    LLM             Gemini 2.5 Flash Ambiguous complaint
                                                   classification only.
                                                   Not used for routing
                                                   logic or data
                                                   decisions.

  Intelligence    Translation     Bhashini API     Translate non-English
                                                   complaint text to
                                                   English before
                                                   classification

  Data            Primary         Supabase         All structured data:
                  Database        (PostgreSQL +    complaints, users,
                                  PostGIS)         assets, wards,
                                                   officers, contractors,
                                                   hotspots

  Data            File Storage    Supabase Storage Proof photos, citizen
                                                   media uploads, voice
                                                   notes

  Data            Auth            Supabase Auth    JWT-based
                                                   authentication and role
                                                   management for
                                                   officers, admins,
                                                   contractors

  Data            Realtime        Supabase         Event bus between
                                  Realtime         backend agents and
                                                   frontend dashboards.
                                                   Replaces Redis pub/sub.

  Presentation    Admin Dashboard Next.js          Role-specific views for
                                  (authenticated   JSSA, AA, FAA, Super
                                  routes)          Admin

  Presentation    Contractor      Next.js          Task list and proof
                  Portal          (authenticated   upload interface for
                                  routes)          contractors

  Scheduling      Cron Jobs       Render Cron Jobs Nightly predictive
                                                   agent execution
  ------------------------------------------------------------------------

**6.3 Data Flow --- End to End**

**Complaint Submission to Assignment**

A citizen submits a complaint via Telegram or the web portal. The
FastAPI backend receives the request, verifies the OTP if it is the
citizen\'s first submission, stores the raw complaint text and any
attached media to Supabase Storage, and creates a complaint record in
the Supabase database with status NEW. If the complaint text is not in
English, it is sent to Bhashini API for translation before storage ---
both the original and translated texts are stored.

Creating the complaint record triggers a Supabase Realtime event. The
Supervisor Agent is subscribed to this event. It wakes up, reads the new
complaint, and begins the agent pipeline: calling the Classification
Agent, then the GeoSpatial Agent, then the Department Routing Agent in
sequence. Each agent writes its results back to Supabase. Each write
triggers another Realtime event that the relevant dashboard components
are subscribed to, so dashboards update in real time without polling.

**Status Updates to Dashboards**

When a JSSA officer updates a complaint\'s status from their dashboard,
the Next.js frontend makes an authenticated API call to FastAPI\'s PATCH
/complaints/{id}/status endpoint. FastAPI validates the transition
against the state machine rules, updates the Supabase record, and
returns success. Supabase Realtime broadcasts the change. All other open
dashboard sessions that are viewing the same complaint or the same ward
map receive the update instantly via their WebSocket connection to
Supabase Realtime.

**Notifications**

Notifications are sent by agents and the FastAPI notification service.
When an agent determines a notification should be sent --- a reminder,
an escalation warning, a survey request --- it calls the notification
service. The service formats the message and sends it via the Telegram
Bot API for Telegram notifications or Twilio for SMS. Notification logs
are written to Supabase for audit purposes.

+-----------------------------------------------------------------------+
| **07**                                                                |
|                                                                       |
| **Technology Stack**                                                  |
|                                                                       |
| Every tool, why it was chosen, and how it connects                    |
+-----------------------------------------------------------------------+

**7.1 Backend --- FastAPI**

FastAPI is a Python web framework built on top of Starlette and
Pydantic. It is chosen for three reasons: it is async by default
(critical for an event-driven system where the backend is frequently
waiting on external services like Gemini, Bhashini, and Supabase), it
generates API documentation automatically from type annotations (which
makes frontend-backend coordination faster), and it is the most
productive Python framework for a small team building quickly.

The FastAPI backend is hosted on Render as a web service. Render handles
SSL termination, auto-deploy on git push, and environment variable
management. The backend is containerised using Docker for consistent
behaviour across local development and production.

**7.2 Frontend --- Next.js**

Next.js is chosen over plain React for two reasons. First, the
public-facing complaint tracking page and public map need to be
server-rendered for fast initial load and SEO --- Next.js handles this
with its App Router and server components. Second, the authenticated
dashboard routes are client-side interactive, which Next.js also handles
cleanly. One framework serves both needs.

The design system uses shadcn/ui with Tailwind CSS. shadcn/ui provides
pre-built, accessible components that can be copied into the project and
customised --- unlike component libraries that are imported as a black
box. All components are styled with Tailwind utility classes. The design
direction is white background, black and dark grey typography, and a
single accent colour (blue-700, hex #1D4ED8) used only for interactive
elements: buttons, active states, and links.

Maps are rendered using MapLibre GL JS, an open-source fork of Mapbox
GL. MapLibre is free with no usage limits and supports custom marker
icons, heatmap layers, and GeoJSON overlays for ward boundaries. The
base map tiles come from OpenStreetMap.

**7.3 Database --- Supabase**

Supabase provides a managed PostgreSQL database with the PostGIS
extension pre-installed. PostGIS adds native geospatial query support
--- the ability to store geometry types (points, polygons), run
proximity queries (\'find all assets within 50 metres of this point\'),
and perform containment checks (\'which ward boundary polygon contains
this coordinate\'). These spatial queries are at the heart of the
GeoSpatial Agent\'s logic.

Supabase also provides: Auth (JWT-based with row-level security
policies, eliminating the need to build auth from scratch), Storage
(S3-compatible file storage for proof photos and citizen media), and
Realtime (WebSocket-based database change broadcasting that replaces
Redis pub/sub and GCP Pub/Sub in this architecture).

Row Level Security (RLS) is enforced at the database level. This means
that even if the API layer has a bug, a JSSA officer cannot read
complaints from a different ward because Supabase will block the query
at the database level based on their JWT role claims.

**7.4 Agent Orchestration --- LangGraph**

LangGraph is an open-source agent orchestration framework from the
LangChain team. It provides a graph-based model for defining agent
workflows: nodes are agent functions, edges are transitions between
agents, and state is passed between nodes as a typed dictionary. This
model maps cleanly to PS-CRM\'s agent design where each agent is a node
and the Supervisor Agent controls which edges are traversed.

LangGraph supports human-in-the-loop checkpoints. At any point in the
agent graph, execution can pause and wait for a human to approve the
next step. In PS-CRM this is used when Gemini\'s classification
confidence is below the threshold --- rather than auto-assigning, the
agent pauses and a human reviewer on the Super Admin dashboard sees the
pending classification and approves or corrects it.

**7.5 LLM --- Gemini 2.5 Flash**

Gemini 2.5 Flash is accessed via the Google AI Studio API using a simple
API key --- no GCP project, no Vertex AI setup required. This keeps
infrastructure costs and complexity low. Gemini 2.5 Flash is chosen over
larger models because it has a fast response time (important for
classification latency), strong multilingual support for Hindi and other
Indian languages, and a generous free tier sufficient for hackathon and
early production usage.

Gemini is used in exactly one place in the system: the Classification
Agent, and only when the rule engine confidence is below 85%. It is not
used for routing decisions, SLA calculations, database queries, or any
other system logic. This boundary is intentional --- LLMs are
unpredictable and expensive. Everything that can be done with
deterministic rules is done with deterministic rules.

**7.6 Translation --- Bhashini API**

Bhashini is the Government of India\'s multilingual AI platform,
providing translation between English and Indian languages including
Hindi, Marathi, Tamil, Telugu, Kannada, and others. It is used in the
intake pipeline to translate non-English complaint text into English
before it reaches the Classification Agent. The original language text
is preserved in the database alongside the translated version.

Bhashini requires API registration through bhashini.gov.in. Approval can
take a few days as it is a government portal. Development can proceed
without it by mocking the translation step --- Gemini 2.5 Flash can
understand Hindi directly, so Bhashini becomes essential for other
regional languages but is not a hard blocker for Hindi-language testing.

**7.7 Messaging --- Telegram Bot API**

The Telegram Bot is created via \@BotFather on Telegram --- a process
that takes under 5 minutes and requires no approval. The bot token is
stored as an environment variable in Render. The bot handles: receiving
complaint submissions from citizens, sending structured replies with
grievance IDs, delivering status update notifications, and running
survey conversations (yes/no confirmation messages).

Telegram is chosen over WhatsApp Business API because Telegram requires
zero approval process, has no per-message fees, and its Bot API is
significantly simpler to integrate. The trade-off is that citizens must
have Telegram installed, whereas WhatsApp has higher penetration in
India. For a hackathon context, Telegram is the correct pragmatic
choice. WhatsApp integration can be added in a future version.

**7.8 Hosting --- Render**

The FastAPI backend is deployed on Render as a web service. Render
supports auto-deploy from GitHub, managed environment variables,
Docker-based deployments, and free-tier Cron Jobs --- which is how the
nightly Predictive Agent is scheduled. The Cron Job points to a specific
Python script entry point in the backend that runs the Predictive Agent
and exits. Render\'s free tier is sufficient for a hackathon demo;
production usage would require the paid tier for persistent services.

+-----------------------------------------------------------------------+
| **08**                                                                |
|                                                                       |
| **API Contract Overview**                                             |
|                                                                       |
| Every endpoint, its inputs, and its outputs                           |
+-----------------------------------------------------------------------+

**8.1 API Design Principles**

All endpoints are REST over HTTPS. The base URL for all endpoints is
/api/v1. Authentication uses JWT tokens in the Authorization header as a
Bearer token, sourced from Supabase Auth. Public endpoints (complaint
status lookup, public map data) require no authentication. All request
and response bodies are JSON. Paginated list endpoints use cursor-based
pagination with a limit and cursor query parameter.

HTTP status codes follow standard conventions: 200 for success, 201 for
created, 400 for bad request (invalid input), 401 for unauthenticated,
403 for unauthorised (wrong role), 404 for not found, 422 for validation
error, 500 for server error. Error responses always include a
machine-readable code and a human-readable message.

**8.2 Complaint Endpoints**

**POST /complaints --- Submit New Complaint**

Creates a new complaint record. This endpoint is public --- no
authentication required, only OTP verification. The request includes:
the citizen\'s verified phone number, the raw complaint text in any
language, latitude and longitude coordinates, an array of media URLs
(files already uploaded to Supabase Storage), and the submission channel
(telegram, web, or call). The response includes the complaint UUID, the
Delhi Mitra-synced grievance ID, the initial status (NEW), and the
estimated SLA in hours based on the detected or default complaint
category.

**GET /complaints/{id} --- Get Complaint Status**

Public endpoint. Returns the non-sensitive status information for a
complaint by its ID. Response includes: current status, department name
(not officer personal details), the status timeline as an ordered array
of events, and any publicly visible notes. Internal notes, officer phone
numbers, and raw classification data are excluded from this response.

**GET /complaints --- List Complaints (Admin)**

Authenticated, role-gated. Returns a paginated list of complaints
filtered by the requesting user\'s scope (JSSA sees only their ward, AA
sees their zone, Super Admin sees all). Supports query filters: status,
ward_id, department_id, category, date_from, date_to, sla_breached
(boolean), and urgency_min. Results are sorted by urgency descending
then by created_at descending by default.

**PATCH /complaints/{id}/status --- Update Complaint Status**

Authenticated. Updates the status of a complaint. The request must
include the new status, an optional internal note, and a proof URL if
the transition requires it (IN_PROGRESS and FINAL_SURVEY_PENDING
transitions both require proof). The backend validates the transition
against the state machine --- invalid transitions return a 400 with an
explanation. On success, the update is written to Supabase, which
triggers a Realtime event to all subscribed dashboard clients.

**8.3 Survey Endpoints**

**POST /complaints/{id}/survey-response --- Record Citizen Survey
Response**

Called internally by the Survey Agent after parsing a citizen\'s
Telegram reply. The request includes the parsed response (approved,
rejected, or no_response) and an optional citizen note. This endpoint
triggers the final state transition: approved leads to CLOSED, rejected
leads to REOPENED with an escalation event, no_response leads to
CLOSED_UNVERIFIED after the 72-hour timeout.

**8.4 Officer and Contractor Endpoints**

**GET /officers/{id}/stats --- Officer Performance**

Returns computed performance metrics for a specific officer: total
complaints ever assigned, total resolved, total escalated, average
resolution time in hours, and reopen rate as a percentage. These metrics
are computed on read from the complaint_events table rather than stored
as counters, ensuring accuracy.

**GET /contractors/{id}/scorecard --- Contractor Scorecard**

Returns the contractor\'s performance record: tasks assigned, tasks
completed on time (before SLA deadline), citizen rejection rate, reopen
rate, and an overall reliability score (0--100) computed from these
metrics using a configurable weighted formula. Also returns a list of
active work orders currently assigned to this contractor.

**PATCH /contractors/{id}/status --- Activate or Deactivate Contractor**

Super Admin only. Sets the contractor\'s active status to true or false.
Deactivated contractors cannot be assigned new work orders. The request
must include a reason, which is logged to the audit trail.

**8.5 Analytics Endpoints**

**GET /analytics/hotspots --- Active Hotspot List**

Returns all currently active predictive hotspots. Each hotspot includes:
the cluster centre coordinates (latitude and longitude), radius in
metres, complaint category, complaint count, severity score (1--5), the
ward it falls in, and the timestamp it was detected. Super Admin only.

**GET /analytics/sla-compliance --- SLA Compliance by Department**

Returns SLA compliance rate as a percentage for each department,
filterable by date range. Also returns the raw counts: total complaints
in range, total resolved within SLA, total breached. Used to populate
the compliance chart on the Super Admin dashboard.

**GET /analytics/complaint-volume --- Complaint Volume Time Series**

Returns complaint counts grouped by time period (day, week, or month
based on query parameter) and optionally grouped by category or ward.
Used to populate the volume chart on the analytics dashboard.

**8.6 Asset and Ward Endpoints**

**GET /assets --- Query Infrastructure Assets**

Returns infrastructure assets near a given location. Query parameters:
lat, lng (required), radius_meters (default 50), and type (optional,
filters by asset type). Used by the GeoSpatial Agent to find nearest
assets and by the frontend map to display asset markers in the admin
view.

**GET /wards --- All Ward Boundaries**

Returns all ward boundary polygons as a GeoJSON FeatureCollection. Used
by the frontend to render ward boundary overlays on the map. This
endpoint is cached aggressively --- ward boundaries do not change
frequently.

+-----------------------------------------------------------------------+
| **09**                                                                |
|                                                                       |
| **Database Schema**                                                   |
|                                                                       |
| Tables, columns, relationships, and rationale                         |
+-----------------------------------------------------------------------+

**9.1 Schema Design Principles**

All primary keys are UUIDs --- never auto-incrementing integers. UUIDs
are safe to generate client-side, do not expose record counts to
external parties, and are required by Supabase\'s RLS system. All tables
include created_at and updated_at timestamps managed automatically by
Supabase triggers. Soft deletes are used where applicable --- records
are marked deleted rather than physically removed, preserving the audit
trail.

**9.2 complaints**

The central table. Every complaint filed in the system has exactly one
row here. The location column is a PostGIS geometry Point --- this
enables all spatial queries. The asset_ids column is a PostgreSQL array
of UUIDs, allowing a complaint to be linked to multiple assets
(important for multi-department complaints). The media_urls column is a
text array of Supabase Storage URLs.

  ----------------------------------------------------------------------------------
  **Column**                  **Type**          **Notes**
  --------------------------- ----------------- ------------------------------------
  id                          UUID              Primary key, generated by default

  grievance_id                VARCHAR(50)       Synced Delhi Mitra ID. Unique.

  citizen_phone_hash          VARCHAR           SHA-256 hash of verified phone
                                                number

  raw_text                    TEXT              Original complaint in submission
                                                language

  translated_text             TEXT              English translation via Bhashini.
                                                Same as raw_text if already English.

  category                    VARCHAR(100)      Classified category: drainage,
                                                streetlight, road, tree, garbage,
                                                etc.

  urgency                     SMALLINT          1 (low) to 5 (critical). Set by
                                                Classification Agent.

  status                      VARCHAR(50)       Current state machine state.
                                                Indexed.

  channel                     VARCHAR(20)       telegram, web, or call

  location                    GEOMETRY(Point,   PostGIS point. SRID 4326 = WGS84
                              4326)             (standard GPS coordinates)

  ward_id                     UUID              FK → wards. Set by GeoSpatial Agent.

  asset_ids                   UUID\[\]          Array of linked asset IDs. Can be
                                                empty if no nearby asset found.

  media_urls                  TEXT\[\]          Supabase Storage URLs for attached
                                                photos or voice notes

  sla_deadline                TIMESTAMPTZ       Computed on classification. Based on
                                                category SLA config.

  llm_used                    BOOLEAN           True if Gemini was invoked during
                                                classification

  classification_confidence   FLOAT             Rule engine confidence score. Below
                                                0.85 triggers LLM.

  created_at                  TIMESTAMPTZ       Auto-managed

  updated_at                  TIMESTAMPTZ       Auto-managed
  ----------------------------------------------------------------------------------

**9.3 complaint_departments**

Junction table handling multi-department routing. When a complaint
involves multiple departments, one row is created per department. Each
row has its own status and assigned officer --- allowing each department
to work independently on their part of the complaint.

  ------------------------------------------------------------------------
  **Column**         **Type**         **Notes**
  ------------------ ---------------- ------------------------------------
  id                 UUID             Primary key

  complaint_id       UUID             FK → complaints

  department_id      UUID             FK → departments

  officer_id         UUID             FK → officers. The JSSA assigned to
                                      this sub-task.

  sub_status         VARCHAR(50)      Independent status per department
                                      sub-task

  sla_deadline       TIMESTAMPTZ      May differ from parent complaint SLA
                                      based on category

  created_at         TIMESTAMPTZ      Auto-managed
  ------------------------------------------------------------------------

**9.4 complaint_events**

Immutable audit log. One row is appended for every state change, agent
action, notification sent, or user interaction. Rows in this table are
never updated or deleted. This table is the source of truth for the
complaint timeline shown to citizens and admins, and it is used to
compute officer performance metrics.

  ------------------------------------------------------------------------
  **Column**         **Type**         **Notes**
  ------------------ ---------------- ------------------------------------
  id                 UUID             Primary key

  complaint_id       UUID             FK → complaints

  event_type         VARCHAR(80)      e.g. status_change, escalation,
                                      notification_sent, agent_action,
                                      citizen_response

  actor_type         VARCHAR(30)      agent, officer, citizen, or system

  actor_id           VARCHAR          Agent name (e.g. \'followup_agent\')
                                      or user UUID

  from_status        VARCHAR(50)      Previous status. Null for
                                      non-status-change events.

  to_status          VARCHAR(50)      New status. Null for
                                      non-status-change events.

  payload            JSONB            Event-specific data: note text,
                                      proof URL, confidence score, etc.

  created_at         TIMESTAMPTZ      Auto-managed. Never updated.
  ------------------------------------------------------------------------

**9.5 assets**

The infrastructure asset registry. This is the table that gives PS-CRM
its asset-level intelligence. Every streetlight, drain, road segment,
tree plot, and water main in Delhi MCD\'s jurisdiction should eventually
have a record here. Assets are seeded from government GIS data if
available, or gradually built from complaint history.

  -------------------------------------------------------------------------
  **Column**         **Type**          **Notes**
  ------------------ ----------------- ------------------------------------
  id                 UUID              Primary key

  asset_type         VARCHAR(80)       pole, drain, road_segment, tree,
                                       water_main, garbage_point

  location           GEOMETRY(Point,   PostGIS point. The physical location
                     4326)             of the asset.

  ward_id            UUID              FK → wards

  department_id      UUID              FK → departments. The department
                                       responsible for this asset.

  external_ref       VARCHAR           Government asset code or GIS ID if
                                       available. Nullable.

  metadata           JSONB             Additional asset attributes: pole
                                       height, drain diameter, road surface
                                       type, etc.

  created_at         TIMESTAMPTZ       Auto-managed
  -------------------------------------------------------------------------

**9.6 wards**

  --------------------------------------------------------------------------------
  **Column**              **Type**            **Notes**
  ----------------------- ------------------- ------------------------------------
  id                      UUID                Primary key

  name                    VARCHAR(100)        Ward name

  boundary                GEOMETRY(Polygon,   PostGIS polygon. Ward boundary for
                          4326)               spatial containment queries.

  primary_department_id   UUID                FK → departments. Default department
                                              for unclassified complaints in this
                                              ward.
  --------------------------------------------------------------------------------

**9.7 officers**

  ------------------------------------------------------------------------
  **Column**         **Type**         **Notes**
  ------------------ ---------------- ------------------------------------
  id                 UUID             Primary key. Matches Supabase Auth
                                      user ID.

  name               VARCHAR(150)     Full name

  role               VARCHAR(30)      jssa, aa, faa, or super_admin

  department_id      UUID             FK → departments

  ward_ids           UUID\[\]         Array of ward IDs in this officer\'s
                                      jurisdiction

  active             BOOLEAN          False if officer account is
                                      suspended

  created_at         TIMESTAMPTZ      Auto-managed
  ------------------------------------------------------------------------

**9.8 contractors**

  ---------------------------------------------------------------------------
  **Column**            **Type**         **Notes**
  --------------------- ---------------- ------------------------------------
  id                    UUID             Primary key. Matches Supabase Auth
                                         user ID.

  name                  VARCHAR(150)     Company or individual name

  contact_email         VARCHAR          For work order notifications

  active                BOOLEAN          False if deactivated by Super Admin.
                                         Cannot receive new work orders.

  deactivation_reason   TEXT             Reason logged when active is set to
                                         false. Nullable.

  created_at            TIMESTAMPTZ      Auto-managed
  ---------------------------------------------------------------------------

**9.9 hotspots**

  -------------------------------------------------------------------------
  **Column**         **Type**          **Notes**
  ------------------ ----------------- ------------------------------------
  id                 UUID              Primary key

  center             GEOMETRY(Point,   Geographic center of the detected
                     4326)             complaint cluster

  radius_meters      INTEGER           Radius of the cluster in metres

  category           VARCHAR(100)      Complaint category the cluster
                                       relates to

  complaint_count    INTEGER           Number of complaints in the cluster

  severity           SMALLINT          1 (low) to 5 (critical). Computed
                                       from density and urgency.

  ward_id            UUID              FK → wards. Ward the cluster center
                                       falls in.

  is_active          BOOLEAN           True until resolved by Super Admin
                                       or cluster dissolves

  detected_at        TIMESTAMPTZ       Timestamp of the nightly job run
                                       that created this record

  resolved_at        TIMESTAMPTZ       Nullable. Set when Super Admin marks
                                       hotspot resolved.
  -------------------------------------------------------------------------

+-----------------------------------------------------------------------+
| **10**                                                                |
|                                                                       |
| **UI Design System**                                                  |
|                                                                       |
| Visual language, layout patterns, and navigation                      |
+-----------------------------------------------------------------------+

**10.1 Design Philosophy**

The PS-CRM interface is designed for professionals who use it for hours
every day. The aesthetic is clean, minimal, and information-dense
without feeling cluttered. White backgrounds, dark grey typography, and
a single accent colour. No dark mode. No gradients. No decorative
elements. Every pixel serves a functional purpose.

The design language is closest to Linear, Notion, or Vercel\'s dashboard
--- tools built for people who care about getting work done, not tools
built to impress in a demo. That said, the public-facing pages
(complaint submission, status lookup, public map) are warmer and more
approachable --- simpler, with more whitespace and friendlier copy.

**10.2 Colour System**

  ------------------------------------------------------------------------
  **Token**          **Hex**       **Usage**
  ------------------ ------------- ---------------------------------------
  Background         #FFFFFF       All page backgrounds

  Surface            #F9FAFB       Card backgrounds, sidebar background

  Border             #E5E7EB       All borders, dividers, table lines

  Text Primary       #111827       Headings, body text, labels

  Text Secondary     #6B7280       Subtitles, metadata, timestamps

  Text Disabled      #9CA3AF       Placeholder text, inactive states

  Accent             #1D4ED8       Primary buttons, active nav items,
                                   links, focus rings

  Accent Light       #EFF6FF       Hover states on accent elements, info
                                   callout backgrounds

  Success            #10B981       Resolved status badges, positive
                                   metrics

  Warning            #F59E0B       Approaching SLA, medium urgency

  Danger             #EF4444       SLA breached, high urgency, error
                                   states

  Neutral Badge      #F3F4F6       Default status badges
  ------------------------------------------------------------------------

  -----------------------------------------------------------------------
  Rule: The accent colour (#1D4ED8) is used ONLY for interactive elements
  --- buttons, active navigation items, links, focus rings, and progress
  indicators. It never appears as a background colour on cards or panels.
  This keeps the interface calm and prevents visual noise.

  -----------------------------------------------------------------------

**10.3 Typography**

  --------------------------------------------------------------------------
  **Style**     **Font**    **Size**        **Weight**   **Usage**
  ------------- ----------- --------------- ------------ -------------------
  Display       Inter       30px / 60px     Bold (700)   Page section
                            line-height                  titles, hero text

  Heading 1     Inter       24px / 32px     Semibold     Page titles, card
                                            (600)        headings

  Heading 2     Inter       18px / 28px     Semibold     Section titles
                                            (600)        within pages

  Heading 3     Inter       16px / 24px     Medium (500) Subsection labels

  Body          Inter       14px / 22px     Regular      All body copy
                                            (400)        

  Small         Inter       12px / 18px     Regular      Timestamps,
                                            (400)        metadata, badge
                                                         labels

  Mono          JetBrains   13px / 20px     Regular      Grievance IDs,
                Mono                        (400)        asset codes, status
                                                         enums
  --------------------------------------------------------------------------

**10.4 Layout Patterns**

**Authenticated Dashboard Shell**

All authenticated pages (JSSA, AA, FAA, Super Admin, Contractor) share
the same shell layout. A fixed left sidebar (240px wide) contains the
primary navigation. The sidebar has a logo at the top, navigation items
in the middle, and the user avatar and name at the bottom. The sidebar
is collapsible to an icon-only state (56px wide) on smaller screens.

A top bar runs across the full width above the content area. It contains
a page title on the left, a global search bar in the centre, and a
notification bell with a badge count and the user avatar on the right.
The top bar is sticky --- it stays visible as the user scrolls.

The content area fills the remaining space. Most pages follow one of two
layouts: a full-width single panel (for analytics, settings, list
views), or a split panel (map on the left, list or detail on the right
--- used for the complaint map view).

**Navigation Hierarchy**

Navigation items are grouped into sections with a small section label.
For a JSSA officer, the navigation contains: Dashboard (map overview),
Complaints (list + filter), and their profile. For a Super Admin, it
additionally contains: Analytics, Contractors, Officers, and Settings.
Navigation items that are not relevant to a user\'s role do not appear
--- the sidebar is dynamically rendered based on role.

Active navigation items use the accent colour as a left border indicator
and a light accent background. Inactive items use secondary text colour.
Hover state uses the surface colour as background.

**Map View --- Complaint Dashboard**

The complaint map view is the primary working interface for JSSA
officers. The screen is split 60/40: the map takes 60% of the width on
the left, and a complaint list panel takes 40% on the right. On screens
narrower than 1280px, the layout stacks vertically with the map on top
and the list below, and the map height is reduced.

The map shows complaint pins as category icons --- not generic dots. A
streetlight complaint shows a light bulb icon. A drainage complaint
shows a water drop icon. Each icon has a coloured border: red for
urgency 4--5, orange for urgency 2--3, grey for urgency 1. When a
complaint is selected (either by clicking the list or clicking the map
pin), the pin expands to a tooltip showing the complaint title and
status. A detail panel slides in from the right side on top of the list
panel.

**Public Complaint Submission Page**

The public page is intentionally simpler than the admin dashboard. It
has a white background with generous padding. A single centred card
contains the complaint form: a text area for the description, a map with
a draggable pin for location, a file upload area for photos, and a
language selector. Below the form is a complaint status lookup: a single
text input where citizens paste their grievance ID to see the current
status and timeline. No sidebar. No top bar. Just the form.

**10.5 Component Standards**

**Cards**

Cards use a white background, a 1px border in the border colour
(#E5E7EB), 4px border radius, and 16--24px internal padding. Cards do
not have drop shadows --- the border provides sufficient visual
separation on a white background. The only exception is the map detail
popup, which uses a subtle shadow to lift it above the map layer.

**Status Badges**

Status badges are small pill labels shown alongside complaints, work
orders, and contractor records. They use a background colour and
matching text colour with no border. NEW is neutral grey. ASSIGNED is
blue (accent light background). IN_PROGRESS is amber. CLOSED is green.
ESCALATED is red. REOPENED is red with a dashed border. Badges are
always rendered in uppercase, 11px, semibold.

**Tables**

Tables are used for list views: complaints list, contractor scorecards,
officer performance. They have a header row with a light grey background
and uppercase 11px column labels. Body rows alternate between white and
the surface colour (#F9FAFB) for readability. Row hover state applies
the border colour as a background. Tables are always paginated --- no
infinite scroll. The pagination control shows the current page range and
total count.

**Forms**

Form inputs have a white background, 1px border in the border colour,
6px border radius, and 14px font size. On focus, the border changes to
the accent colour and a light accent box shadow appears. Error states
use the danger colour for the border and show an error message below the
input in 12px danger-coloured text. Labels sit above inputs, never
inside them as placeholders. Placeholder text uses the disabled text
colour for guidance only.

**Buttons**

Primary buttons use the accent colour as background with white text.
Hover state darkens the background by 10%. Secondary buttons use white
background with accent border and accent text. Destructive buttons
(deactivate contractor, reopen complaint) use the danger colour. All
buttons have 6px border radius, 14px semibold text, and 10px horizontal
padding. Buttons in a loading state show a spinner and disable
interaction.

+-----------------------------------------------------------------------+
| **11**                                                                |
|                                                                       |
| **Development Phases**                                                |
|                                                                       |
| Three phases from setup to production-ready                           |
+-----------------------------------------------------------------------+

**11.1 Phase Overview**

Development is split into three sequential phases. Each phase has a
clear scope, a defined end state, and a set of verification checks that
must all pass before moving to the next phase. No phase begins until the
previous phase is verified. This prevents the common failure mode of
building on top of broken foundations.

+---+-------------------------------------------------------------------+
| * | **Foundation --- Core Intake, Classification, and Database**      |
| * |                                                                   |
| P | **Weeks 1--3**                                                    |
| 1 |                                                                   |
| * | Set up the entire infrastructure, get a complaint from submission |
| * | to classification and assignment. No agents yet --- just the      |
|   | pipeline.                                                         |
+---+-------------------------------------------------------------------+

+---+-------------------------------------------------------------------+
| * | **Intelligence --- Agents, SLA, Surveys, and Dashboards**         |
| * |                                                                   |
| P | **Weeks 4--6**                                                    |
| 2 |                                                                   |
| * | Build and wire all agents. Build the admin dashboard. Real-time   |
| * | updates working. Full complaint lifecycle functional.             |
+---+-------------------------------------------------------------------+

+---+-------------------------------------------------------------------+
| * | **Analytics, Prediction, and Polish**                             |
| * |                                                                   |
| P | **Weeks 7--9**                                                    |
| 3 |                                                                   |
| * | Predictive agent, Super Admin analytics, contractor scorecards,   |
| * | public map, notification polish, and demo preparation.            |
+---+-------------------------------------------------------------------+

**11.2 Phase 1 --- Foundation**

**Scope**

Phase 1 establishes the entire technical foundation. By the end of this
phase, a complaint can be submitted via Telegram or the web form,
translated if necessary, classified by the rule engine (and Gemini for
ambiguous cases), geo-tagged to an asset and ward, assigned to the
correct JSSA queue, and visible in a basic list view. No agent
automation yet --- everything is triggered directly by API calls.

**Phase 1 Deliverables**

-   Supabase project configured with all tables, PostGIS extension
    enabled, RLS policies for all roles

-   Supabase Auth set up with role claims (jssa, aa, faa, super_admin,
    contractor) in JWT

-   FastAPI project scaffolded on Render with environment variables
    configured

-   Next.js project scaffolded with shadcn/ui, Tailwind, and MapLibre
    installed

-   Telegram bot created and connected to FastAPI webhook

-   Bhashini API integrated --- translation working for Hindi input

-   Complaint intake endpoint functional: OTP verification, storage,
    grievance ID generation

-   Delhi Mitra sync stub (mock response if no real API available)

-   Classification rule engine implemented with initial keyword
    dictionary

-   Gemini 2.5 Flash integration for low-confidence classification

-   GeoSpatial Agent logic: PostGIS asset lookup and ward containment
    query

-   Department Routing logic: single and multi-department assignment

-   Basic authenticated complaint list view in Next.js (table only, no
    map)

-   Basic public complaint status lookup by grievance ID

-   Ward boundary GeoJSON seeded into Supabase

-   Delhi MCD asset registry initial seed (at minimum 50 test assets
    across 3 wards)

**Phase 1 Verification Checks**

  -----------------------------------------------------------------------
  All checks below must pass before Phase 2 begins. Run each check
  manually and document the result.

  -----------------------------------------------------------------------

  -------------------------------------------------------------------------------
  **\#**   **Check**          **How to Verify**      **Pass Condition**
  -------- ------------------ ---------------------- ----------------------------
  1.1      Supabase schema    Run EXPLAIN ANALYZE on Query returns results in
           integrity          a spatial query:       under 200ms. PostGIS
                              SELECT \* FROM assets  extension confirmed active.
                              WHERE                  
                              ST_DWithin(location,   
                              ST_MakePoint(77.209,   
                              28.613)::geography,    
                              50)                    

  1.2      RLS enforcement    Log in as a JSSA user  Query returns 0 results. RLS
                              and attempt to query a blocks access.
                              complaint from a       
                              different ward via     
                              Supabase client        
                              directly               

  1.3      Telegram bot       Send a complaint       Bot responds with a
           intake             message in Hindi to    grievance ID within 10
                              the Telegram bot with  seconds. Record visible in
                              a shared location      Supabase complaints table
                                                     with raw and translated
                                                     text.

  1.4      Web form intake    Submit a complaint via Complaint record in Supabase
                              the web form with a    has correct location
                              photo attachment and   geometry, media_url pointing
                              map pin                to Supabase Storage, and
                                                     status = NEW.

  1.5      OTP verification   Attempt to submit a    API returns 401. Submission
                              complaint with an      is blocked.
                              unverified phone       
                              number                 

  1.6      Bhashini           Submit a complaint in  translated_text in Supabase
           translation        Hindi: \'मेरे घर के पास   record reads as English.
                              नाला बह रहा है\'        raw_text preserves original
                                                     Hindi.

  1.7      Rule engine        Submit: \'streetlight  Complaint classified as
           classification --- is broken on main      category=streetlight,
           high confidence    road\'                 department=Electricity,
                                                     llm_used=false,
                                                     classification_confidence
                                                     \>= 0.85

  1.8      LLM classification Submit: \'something is classification_confidence \<
           --- low confidence broken near the market 0.85 in record,
                              and it is causing      llm_used=true, Gemini has
                              issues for everyone\'  returned a category and
                                                     departments

  1.9      Multi-department   Submit: \'tree is      Two rows in
           split              touching the           complaint_departments table:
                              electricity pole near  one for Forest Department,
                              school\'               one for Electricity
                                                     Department

  1.10     GeoSpatial asset   Submit a complaint     Complaint record has
           linking            with coordinates       asset_ids containing the
                              within 50m of a seeded seeded asset\'s UUID
                              test asset             

  1.11     Ward assignment    Submit complaints from Each complaint has the
                              coordinates in three   correct ward_id matching the
                              different seeded ward  ward whose boundary polygon
                              boundaries             contains the coordinates

  1.12     Authenticated list Log in as a JSSA,      Only complaints in their
           view               navigate to the        ward are visible. Complaints
                              complaints list        from other wards are absent.

  1.13     Public status      Navigate to /status    Status, timeline, and
           lookup             and enter a grievance  department name are visible.
                              ID                     Officer personal contact
                                                     details are absent.

  1.14     Render deployment  Push a code change to  Render auto-deploys within 3
                              main branch            minutes. Health check
                                                     endpoint returns 200.
  -------------------------------------------------------------------------------

**11.3 Phase 2 --- Intelligence**

**Scope**

Phase 2 activates the agent layer and builds the full admin dashboard.
By the end of this phase, the complete complaint lifecycle is
functional: complaints are routed automatically, SLA deadlines are
monitored, reminders and escalations are sent without manual
intervention, citizens receive surveys via Telegram, and all status
changes appear in real time on the admin dashboard. The map view is
live.

**Phase 2 Deliverables**

-   LangGraph Supervisor Agent wired to Supabase Realtime --- triggers
    on new complaint creation

-   Classification Agent integrated into LangGraph graph

-   GeoSpatial Agent integrated into LangGraph graph

-   Department Routing Agent integrated into LangGraph graph

-   Follow-Up Agent running continuously, subscribed to ASSIGNED and
    IN_PROGRESS complaints

-   SLA reminders sending via Telegram at 50% and 90% thresholds

-   Auto-escalation at 100% SLA breach --- complaint_events log entry,
    officer escalation count incremented

-   Survey Agent sending mid-resolution Telegram message and parsing
    citizen response

-   Survey Agent sending final resolution Telegram message and
    triggering CLOSED or REOPENED transition

-   Contractor Agent blocking status transitions when proof photo is
    missing

-   MapLibre map view in admin dashboard with category icons and
    urgency-colour borders

-   Complaint detail panel --- slides in on pin click without leaving
    map

-   Status update actions from detail panel --- JSSA can update status,
    upload proof, add note

-   Supabase Realtime subscription in frontend --- map pins and list
    update without page refresh

-   JSSA notification: Telegram message on new complaint assignment

-   AA notification: Telegram message on escalation

-   Complaint timeline view --- ordered list of complaint_events shown
    in detail panel

-   Human-in-loop review queue: complaints where Gemini confidence was
    below threshold appear in a review queue for Super Admin to manually
    classify

**Phase 2 Verification Checks**

  -----------------------------------------------------------------------
  All checks below must pass before Phase 3 begins.

  -----------------------------------------------------------------------

  ----------------------------------------------------------------------------------
  **\#**   **Check**          **How to Verify**         **Pass Condition**
  -------- ------------------ ------------------------- ----------------------------
  2.1      Supervisor Agent   Submit a new complaint    Within 30 seconds of
           trigger            via Telegram and watch    submission, complaint_events
                              Supabase complaint_events contains rows for:
                              table                     classification_start,
                                                        geospatial_lookup,
                                                        department_routing,
                                                        status_change
                                                        (NEW→CLASSIFIED→ASSIGNED)

  2.2      Agent idempotency  Manually insert a         Agent does not process the
                              duplicate complaint event duplicate. complaint_events
                              into Supabase Realtime    does not have duplicate
                                                        action rows.

  2.3      JSSA assignment    Submit a complaint that   JSSA\'s Telegram account
           notification       routes to a seeded JSSA   receives an assignment
                                                        notification within 60
                                                        seconds

  2.4      SLA 50% reminder   Set a test complaint\'s   JSSA receives a Telegram
                              sla_deadline to 2 hours   reminder. complaint_events
                              from now and sla_window   logs a notification_sent
                              to 4 hours (50% elapsed)  event.

  2.5      SLA escalation     Set a test complaint\'s   Within 5 minutes, complaint
                              sla_deadline to 1 minute  gains ESCALATED flag.
                              in the past               complaint_events contains
                                                        escalation event. AA
                                                        receives Telegram
                                                        notification.

  2.6      Proof gate         Attempt to call PATCH     API returns 400 with error:
           enforcement        /complaints/{id}/status   proof_url is required for
                              with                      this transition
                              to_status=IN_PROGRESS and 
                              no proof_url              

  2.7      Mid-survey         Manually trigger Survey   Citizen Telegram account
           Telegram message   Agent for a test          receives survey message
                              complaint in              within 60 seconds
                              MID_SURVEY_PENDING        

  2.8      Survey approval    Reply \'yes\' to the      Complaint status transitions
           flow               final survey Telegram     to CLOSED. complaint_events
                              message                   has citizen_response event
                                                        with response=approved.

  2.9      Survey rejection   Reply \'no\' to the final Complaint status transitions
           flow               survey Telegram message   to REOPENED. Escalation
                                                        event logged. AA notified.

  2.10     72-hour auto-close Set a test complaint to   Complaint transitions to
                              FINAL_SURVEY_PENDING and  CLOSED_UNVERIFIED.
                              set survey_sent_at to 73  complaint_events logs
                              hours ago                 timeout event.

  2.11     Real-time map      Open admin dashboard map  Pin colour updates on the
           update             in one browser. Update a  first browser\'s map within
                              complaint status from     3 seconds without page
                              another browser.          refresh.

  2.12     Human review queue Submit a complaint        Complaint appears in review
                              designed to get low       queue in Super Admin
                              confidence (vague text)   dashboard. Status is
                                                        CLASSIFIED with a
                                                        needs_review flag.

  2.13     Multi-department   Submit a                  Parent complaint status is
           independent        tree-touching-pole        still IN_PROGRESS. CLOSED
           lifecycle          complaint and advance one status only shows after both
                              sub-task to CLOSED while  sub-tasks are closed.
                              the other stays           
                              IN_PROGRESS               

  2.14     Complaint timeline Open a complaint that has Detail panel shows all
                              gone through 5+ state     transitions in correct
                              transitions               chronological order with
                                                        actor type and timestamp.
  ----------------------------------------------------------------------------------

**11.4 Phase 3 --- Analytics, Prediction, and Polish**

**Scope**

Phase 3 completes the product. Predictive hotspot detection is
operational. The Super Admin analytics dashboard is fully built.
Contractor scorecards are computed and displayed. The public map is
live. The interface is polished and ready for a demo. All edge cases
identified in Phase 1 and Phase 2 testing are resolved.

**Phase 3 Deliverables**

-   Predictive Agent implemented with DBSCAN clustering on complaint
    history

-   Render Cron Job configured to run Predictive Agent nightly at 2:00
    AM

-   Hotspots table populated with real test data

-   Super Admin hotspot map with severity-coloured cluster circles

-   Super Admin analytics: complaint volume time-series chart (Recharts)

-   Super Admin analytics: SLA compliance chart by department

-   Contractor scorecard table with computed on-time rate, rejection
    rate, reliability score

-   Contractor deactivation flow with reason logging

-   Officer performance table for AA view

-   Public map page: ward-level complaint density, no sensitive data

-   Telegram bot refined: structured messages with clear copy,
    emoji-free

-   Mobile responsive: all pages functional on 375px--768px screen
    widths

-   Error handling: all API errors return structured JSON. Frontend
    shows toast notifications for all errors and successes

-   Loading states: all data-fetching components show skeleton loaders

-   Empty states: all list and map views show a meaningful empty state
    when there is no data

-   Demo seed data: 50+ realistic complaints across 5 wards, 3 complaint
    categories, in various lifecycle states

**Phase 3 Verification Checks**

  -----------------------------------------------------------------------
  All checks below must pass before demo readiness is declared.

  -----------------------------------------------------------------------

  -----------------------------------------------------------------------------
  **\#**   **Check**        **How to Verify**      **Pass Condition**
  -------- ---------------- ---------------------- ----------------------------
  3.1      Predictive agent Seed 7 drainage        One hotspot record created
           clustering       complaints within 150m in Supabase with
                            radius in the past 14  category=drainage,
                            days, then run         complaint_count=7,
                            Predictive Agent       is_active=true
                            manually               

  3.2      Hotspot Realtime Run Predictive Agent   Hotspot appears on Super
           push             while Super Admin      Admin map within 5 seconds
                            dashboard is open      of agent completion without
                                                   page refresh

  3.3      Cron job         Trigger the Render     Job completes without error.
           execution        Cron Job manually from Render logs show successful
                            the Render dashboard   run. Hotspots table updated.

  3.4      Complaint volume Navigate to Super      Chart renders with correct
           chart            Admin analytics        complaint counts per day for
                                                   the past 30 days, matching
                                                   raw Supabase query results

  3.5      SLA compliance   Manually verify: count API response matches manual
           calculation      complaints resolved    calculation within 1%
                            before sla_deadline    
                            divided by total       
                            resolved complaints in 
                            date range             

  3.6      Contractor       For a test contractor  on_time_rate = 70%,
           scorecard        with 10 tasks (7       rejection_rate = 20%,
           accuracy         on-time, 2             reopen_rate = 10%
                            citizen-rejected, 1    
                            reopened), check the   
                            scorecard              

  3.7      Contractor       Deactivate a test      Contractor\'s active = false
           deactivation     contractor via Super   in Supabase. Attempting to
                            Admin panel            assign a new work order to
                                                   this contractor returns 400.

  3.8      Public map       Open public map        Map shows ward-level
                            without logging in     complaint density. No
                                                   officer names, phone
                                                   numbers, or internal notes
                                                   visible. No authentication
                                                   required.

  3.9      Mobile           Open admin dashboard   All pages are usable. No
           responsiveness   on a 375px-wide        horizontal scroll. Map is
                            viewport (iPhone SE)   accessible. Sidebar
                                                   collapses to icon-only mode.

  3.10     Error handling   Simulate a Gemini API  Classification Agent falls
                            failure by providing   back to rule engine result
                            an invalid API key     or queues for human review.
                            temporarily            No 500 error surfaced to
                                                   citizen. Error logged to
                                                   complaint_events.

  3.11     Loading states   Throttle network to    Skeleton loaders appear
                            Slow 3G in browser     immediately. No layout shift
                            DevTools and navigate  when data loads.
                            to the complaint list  

  3.12     Empty state      Log in as a JSSA with  Map view shows a centred
                            no complaints assigned empty state message: \'No
                                                   active complaints in your
                                                   ward.\' Not a blank map.

  3.13     Full demo run    Run the complete       Each step completes without
                            citizen-to-closure     error. Status visible on
                            flow end to end with a public portal throughout.
                            live demo: file via    All 3 dashboards (public,
                            Telegram → classify →  JSSA, Super Admin) reflect
                            assign → officer       correct state at each step.
                            updates → survey →     
                            closure                

  3.14     Performance ---  Use a load testing     p95 response time under
           API response     tool to send 50        400ms. No 5xx errors.
           time             concurrent requests to 
                            GET /complaints        
  -----------------------------------------------------------------------------

+-----------------------------------------------------------------------+
| **12**                                                                |
|                                                                       |
| **Non-Functional Requirements**                                       |
|                                                                       |
| Performance, security, and compliance                                 |
+-----------------------------------------------------------------------+

**12.1 Performance**

  -----------------------------------------------------------------------
  **Requirement**                     **Target**
  ----------------------------------- -----------------------------------
  API response time (non-LLM          \< 300ms
  endpoints, p95)                     

  LLM classification time (Gemini     \< 5 seconds
  call)                               

  Map initial load time               \< 2 seconds on 4G connection

  Supabase Realtime update latency    \< 3 seconds from DB write to UI
                                      update

  Predictive Agent nightly run        \< 10 minutes for 90-day complaint
  completion                          history

  Concurrent users supported (V1)     500 simultaneous dashboard users
  -----------------------------------------------------------------------

**12.2 Security**

  -----------------------------------------------------------------------
  **Requirement**        **Implementation**
  ---------------------- ------------------------------------------------
  Authentication         Supabase Auth JWT. All non-public endpoints
                         require valid token.

  Authorisation          Row Level Security in Supabase enforced at
                         database level. API role checks as second layer.

  Citizen phone storage  SHA-256 hashed. Never stored in plaintext. Never
                         returned in any API response.

  Officer contact        Officer phone numbers never exposed in public
  privacy                API responses or public dashboard.

  Internal notes privacy Notes marked internal=true are excluded from all
                         public and citizen-facing API responses.

  File upload validation Supabase Storage policies restrict uploads to
                         image MIME types only. Max file size 10MB.

  Audit trail integrity  complaint_events table has no UPDATE or DELETE
                         RLS permissions. Append-only.

  Environment secrets    All API keys stored as Render environment
                         variables. Never committed to version control.
  -----------------------------------------------------------------------

**12.3 Data Retention**

  -----------------------------------------------------------------------
  **Data Type**          **Retention Policy**
  ---------------------- ------------------------------------------------
  Complaint records      7 years minimum (government compliance
                         requirement)

  Complaint events       7 years. Immutable.
  (audit log)            

  Proof photos and media Active for 2 years. Archived to cold storage
  (Supabase Storage)     tier after 2 years.

  Hotspot records        Retained indefinitely. Historical hotspot data
                         informs future predictions.

  Contractor and officer Retained indefinitely. Deactivated records
  profiles               marked inactive, not deleted.

  Citizen phone hashes   Retained for duration of complaint history. Not
                         linked to personally identifiable data.
  -----------------------------------------------------------------------

**12.4 Accessibility**

-   All interactive elements must be keyboard navigable

-   All form inputs must have associated labels --- no placeholder-only
    labelling

-   Colour is never the sole means of conveying information --- status
    badges include text labels alongside colour

-   Map functionality must degrade gracefully if MapLibre fails to load
    --- a list view must remain usable

-   Minimum touch target size on mobile: 44x44px for all buttons and
    interactive elements

+-----------------------------------------------------------------------+
| **PS-CRM · Product Requirements Document**                            |
|                                                                       |
| Team BlackHaze · Vishwakarma Institute of Technology · Version 1.0    |
|                                                                       |
| FastAPI · Next.js · Supabase · LangGraph · Gemini 2.5 Flash ·         |
| Telegram · Bhashini · Render                                          |
+-----------------------------------------------------------------------+
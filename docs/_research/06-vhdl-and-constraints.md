# 06 — VHDL and Constraints for LLM Agents (Vivado / 7-series & Zynq-7000)

**Purpose.** Reference note for an LLM (or a human reviewer) that must *write*, *review*
and *constrain* synthesizable VHDL for AMD/Xilinx FPGAs with Vivado, and that must be
able to say **why** a construct is wrong, not just that it is.

**Scope.** Tool flow: Vivado (project and non-project mode), device families Artix-7,
Kintex-7, Spartan-7, Zynq-7000 (PL side) and — where noted — Zynq UltraScale+ / Versal.
No HLS, no Vitis kernel code, no simulation-only constructs except where they are
explicitly flagged as *testbench-only*.

**How to read citations.** Every non-obvious claim carries a bracketed label such as
`[UG903 §Primary Clocks Examples]`. Labels map to exact URLs and document versions in
**§8 Sources** (one table for documents, one table for the individual topics used).
Statements that are language-level (IEEE VHDL) rather than AMD-specific are marked
`[IEEE 1076]`. Statements that are engineering reasoning rather than a quoted doc fact
are marked `[derived]`.

**Verification status.** Everything cited was read from the official document (the
online Fluid Topics editions for 2026.1 tools, plus the downloadable PDFs for the
7-series device guides). Nothing in this note was produced by running Vivado — no EDA
tool is installed on the machine that produced it. Where a claim could only be checked
in an older revision of a document, the revision is stated.

---

## 0. Tools, versions and language level

| Item | Status / version | Note |
|---|---|---|
| Vivado tool flow | 2026.1 (doc set) | UG901/903/906/908/949/973/994/1118/835 all read at the 2026.1 edition |
| Timing closure quick reference | UG1292 **v2025.1** (2025-05-29) | the only current revision published as PDF |
| 7-series clocking | UG472 **v1.14** (2018-07-30) | frozen document, architecture unchanged |
| 7-series packaging/pinout | UG475 **v1.20** (2024-03-13) | current |
| Zynq-7000 TRM | UG585 **v1.15** | current |
| Libraries guides (UG953 / UG974) | last published **2020.1 / 2020.1** | discontinued; use UG901 + `report_property`/`get_property` instead |
| Designing with IP | UG896, last edition **2020.2** | partially superseded by UG1118 + UG994 |
| VHDL language | IEEE 1076-2002 by default, **VHDL-2008 optional** (`synth_design -vhdl2008`, UG901 ch. *VHDL-2008 Language Support*) | the LLM must never assume 2008-only syntax unless the flow sets it |

Supported host OS for the Vivado 2026.1 installer (relevant when the agent generates
install scripts or CI containers): Windows 10 22H2 / 11 23H2–25H2, RHEL 8.10–10.1,
SUSE SLES 15 SP4/SP6/SP7, Amazon Linux 2 AL2023 LTS, AlmaLinux 8.10–10.1, Ubuntu
22.04.x and 24.04.x (64-bit), Rocky 8.10–10.1 `[UG973 §Supported Operating Systems]`.
Ubuntu requires `libtinfo.so.5` (AR# 76616, quoted in the same topic).

**Rule for agents:** target plain VHDL-93/2002 syntax. Use VHDL-2008 only when the
project explicitly compiles with 2008 semantics, because a file that uses
`process (all)`, `std.env`, `context`, generic-package or `-2008` conditional analysis
will fail to elaborate in a default 2002 project.

---

## 1. Synthesizable VHDL — the mistakes an LLM makes most often

### 1.0 The ground truth from UG901

Vivado synthesis supports "VHDL design entities and configurations except as noted in
the following table" `[UG901 §VHDL Constructs Support Status]`. The rows below are
quoted or paraphrased from that table (2026.1 edition) because they are exactly the
constructs an LLM tends to produce:

| Construct | Support status (UG901) |
|---|---|
| Ports | Supported, including unconstrained ports |
| Entity statement part | **Unsupported** |
| `TIME` / `REAL` physical types | Supported **only in functions for constant calculations** |
| Deferred constant | Unsupported |
| Register and bus type signals | Unsupported |
| Leading underscore in an object name (`_DATA_1`) | Not allowed |
| Abstract literals | Only integer literals |
| Physical literals | **Ignored** |
| Allocators | Unsupported |
| `Wait ... for time_expression` | **Unsupported** |
| `Wait on sens_list until boolean_expr` | Supported with one signal, **multiple waits not supported**, no latch via wait |
| Concurrent signal assignment with **`after`** clause / `transport` / `guarded` | **Not supported** (plain assignments supported; `UNAFFECTED` supported) |
| Signal assignment statement | Supported — **"Delay is ignored"** |
| `for-generate` | Constant bounds only |
| `if-generate` | Static condition only |
| `/` | Only if right operand is a **constant power of 2**, or both operands constant |
| `rem`, `mod` | Only if right operand is a constant power of 2 |
| `**` | Only if the **left operand is 2** |
| Concurrent assertion statement | Ignored |

Additional behaviour, same document: sequential logic is *by definition* the process
where "some assigned signals are not explicitly assigned in all paths", which produces
state (flip-flops or latches) `[UG901 §VHDL Sequential Logic]`; combinational logic is
described with concurrent signal assignments whose textual order is irrelevant
`[UG901 §VHDL Combinatorial Circuits]`; and a sequential process must list in its
sensitivity list "the clock signal" plus "all asynchronous control signals"
`[UG901 §Flip-Flops, Registers, and Latches]`.

### 1.1 The table — bad code vs. good code

Each row: the failure mode an LLM produces, a minimal **bad** snippet, the **good**
replacement, and the rule with its source.

| # | Mistake | Bad (typical LLM output) | Good | Rule & source |
|---|---|---|---|---|
| 1 | **Timing delays in RTL** (`after`) | `q <= d after 5 ns;` | `q <= d;` (put the delay in the testbench: `wait for 5 ns;`) | The `after` clause is not supported on concurrent signal assignments, and a signal-assignment delay is *ignored* anyway `[UG901 §VHDL Constructs Support Status]` |
| 2 | **Simulation-only waits in RTL** | `wait for 10 ns;` inside a design process | Remove it; use `if rising_edge(clk)` in a sensitivity-list process | `Wait for time_expression` → *Unsupported* `[UG901 §VHDL Constructs Support Status]` |
| 3 | **`wait until` misuse** | Two `wait until` statements, or a latch described with `wait`, or a process that has both a sensitivity list and a wait | One `wait until rising_edge(clk);` as the first statement, in a process *without* sensitivity list, or better: use a sensitivity-list process | Supported with restrictions: one signal in the list and in the boolean expression, no multiple waits, no latch via wait `[UG901 §VHDL Constructs Support Status]`; "the same sequential process cannot have both a sensitivity list and a wait statement" `[UG901 v2018.1 ch. VHDL Support]` |
| 4 | **Variables used where signals are meant** | `variable v_out : std_logic;` then `v_out := ...` and reading `v_out` from *another* process or expecting it to appear on a port at the end of the delta | Declare process-local temporaries as variables, everything that crosses a process boundary or reaches a port as a signal (`s_*` / `o_*`) | Variables are local objects of a process; signals are the resolved inter-process objects. Reading a variable assigned later in the same process gives the *old* value only if you read before the assignment — the classic "variable in output of process" bug `[IEEE 1076]` |
| 5 | **Unintended latch** | Combinational process with `if sel = '1' then q <= a; end if;` (no `else`) or a `case` without `when others` | Assign a default for every output at the top of the process, then override: `q <= a; if sel = '1' then q <= b; end if;` | "Inferred Latches are often the result of HDL coding mistakes, such as incomplete if or case statements"; Vivado warns `WARNING: [Synth 8-327] inferring latch for variable 'Q_reg'` `[UG901 §Latches Reporting Example]` (the first sentence is quoted from **UG901 v2018.1 §Latches**; the 2026.1 reader serves that section without body text) |
| 6 | **Incomplete / wrong sensitivity list** | Clocked process listed as `process (d, rst)` ; combinational process listing only some of the read signals | `process (i_clk)` for a synchronous process (plus async resets if any); combinational: list **all** signals read, or use VHDL-2008 `process (all)` | "The process or always block sensitivity list must list: the clock signal; all asynchronous control signals" `[UG901 §Flip-Flops, Registers, and Latches]`. For a clocked process written with `rising_edge()`, the sensitivity list must contain the clock (and the async reset)  `[UG901 §VHDL Sequential Logic]` |
| 7 | **No initialisation / no reset at all** | Signals never reset; agent assumes "it starts at 0 in simulation, so it's fine" | Set a default at declaration (`signal s_cnt : unsigned(7 downto 0) := (others => '0');`) **and** implement an explicit reset path | "To initialize the content of a Register at circuit power-up, specify a default value for the signal during declaration"; the initialisation value must be a constant (may come from a function call) `[UG901 §Flip-Flops and Registers Initialization, §VHDL Initial Values and Operational Set/Reset]`. Initial values are a power-up convenience, not a substitute for reset discipline `[derived]` |
| 8 | **`real` in synthesizable code** | `signal s_gain : real := 0.8;` / `o_y <= integer(s_gain * real(i_x));` | Compute the fixed-point/integer coefficient offline: `constant C_GAIN_Q10 : natural := 819;` and do integer arithmetic in `numeric_std` | `REAL` is supported "only in functions for constant calculations"; "You cannot define a synthesizable object of type real" `[UG901 §VHDL Constructs Support Status; UG901 v2018.1 ch. VHDL Support]`. Same for `TIME` |
| 9 | **Arithmetic on `std_logic_vector` without conversion** | `sum <= a + b;` where both are `std_logic_vector` | `sum <= std_logic_vector(unsigned(a) + unsigned(b));` | The type family you need is `numeric_std`; `std_logic_vector` has no arithmetic operators `[IEEE 1076 / std_logic_1164]`. Vivado synthesis supports type conversions and the `+ - * /` operators within their stated limits `[UG901 §VHDL Constructs Support Status]` |
| 10 | **Mixing `signed` and `unsigned` (or legacy `std_logic_arith`)** | `use ieee.std_logic_arith.all; use ieee.std_logic_unsigned.all;` then `if slv > 5 then` | `use ieee.numeric_std.all;` then `if unsigned(slv) > to_unsigned(5, slv'length) then` | Vivado keeps legacy IEEE packages for compatibility (`VHDL Legacy Packages` section; `std_logic_arith` is supported as a *legacy* package), but overload ambiguity and "unsigned/signed" mixing is a classic elaboration failure `[UG901 §VHDL Predefined Packages + revision history]` |
| 11 | **Comparing/assigning vectors of different widths** | `if cnt = "100" then` when `cnt` is 8 bits; `o_big <= i_small;` | `if cnt = std_logic_vector(to_unsigned(4, cnt'length)) then`; explicit resize: `o_big <= std_logic_vector(resize(unsigned(i_small), o_big'length));` | VHDL performs **no implicit resizing**; a length mismatch is a type/elaboration error, not a warning `[IEEE 1076]`. `resize`, `to_unsigned`, `to_integer` are the correct tools `[IEEE 1076 / numeric_std]` |
| 12 | **`downto` vs `to` inconsistency** | Entity declares `port (i_d : in std_logic_vector(0 to 7));` while the internal buffer is `(7 downto 0)`, or a port map swaps directions | Pick **`downto`** for all vectors (MSB on the left), and keep it everywhere: entity, signals, generics, IP port maps | A direction reversal is legal but silently reverses the bit order through a port map, producing bit-swapped data and confusing `'length`-based code. Consistency is the only defence; Vivado accepts both `to` and `downto` for ports `[UG901 §VHDL Constructs Support Status (ports, type declarations)]` `[derived]` |
| 13 | **Multi-driver** | The same signal assigned in two different processes (`s_busy <= ...` in `p_a` and in `p_b`) | One process per signal: `p_seq` owns state, `p_comb` owns the combinational outputs it exclusivly drives | Two drivers on a non-resolved `std_logic` design is a VHDL resolution error / 'X' in simulation. Note that *different elements of the same array* (a memory written in two processes) are also multiple drivers `[IEEE 1076]` |
| 14 | **Combinational output written inside a clocked process** | Wanting a pure combinational `o_y` but computing it inside `if rising_edge(clk)` | Either move the computation to a concurrent assignment or a combinational process, or *accept and document* the extra pipeline stage | Anything assigned inside a clocked process becomes registered (or latched) state; "a VHDL process is sequential when some assigned signals are not explicitly assigned in all paths" `[UG901 §VHDL Sequential Logic]` |
| 15 | **Synchronous / asynchronous reset mixed up** | Async reset declared in the sensitivity list but "used" with a synchronous `if rst = '1' then` *inside* `rising_edge`, or vice versa: a reset tested before `rising_edge` while being absent from the sensitivity list | Decide once: **synchronous** → `if rising_edge(clk) then if rst = '1' then ... end if; end if;` (sensitivity list = clock only). **Asynchronous** → `process (clk, rst) begin if rst = '1' then ... elsif rising_edge(clk) then ... end if; end process;` | Sensitivity list must contain the clock and all asynchronous controls `[UG901 §Flip-Flops, Registers, and Latches]`; "you cannot describe a sequential element with asynchronous control logic using a process without a sensitivity list" `[UG901 v2018.1 ch. VHDL Support]`. Vivado also provides `DIRECT_RESET` / `EXTRACT_RESET` attributes to control whether a reset is pushed into the FF or extracted as a LUT input `[UG901 §DIRECT_RESET, §EXTRACT_RESET]` |
| 16 | **Gated clock built by hand** | `s_clk_gated <= i_clk and i_en;` then `if rising_edge(s_clk_gated)` | Keep one clock; generate a **clock enable**: `if rising_edge(i_clk) then if i_en = '1' then ... end if; end if;` | Combinational logic in a clock path makes delay and skew unpredictable `[UG1292 §Improving Clock Skew Techniques]`; a real gated clock must go through `BUFGCE`/`BUFGCTRL` (see §2.6) `[UG949 §7 Series Device Clocking]` |
| 17 | **Generics misused** | `for i in 0 to g_depth-1 generate` with `g_depth` of an unconstrained/subtype-free kind; `if g_width > 4 generate` with a non-static expression; a `for-generate` loop bounded by a signal | Declare generics as `natural`/`positive`/`std_logic`; use them only in static expressions; `if-generate` only with a **static condition** | `for-generate` is supported "for constant bounds only", `if-generate` "for static condition only" `[UG901 §VHDL Constructs Support Status]` |
| 18 | **Vector arithmetic needing `/`, `mod`, `rem` by a non power of 2** | `y <= a / 10;` | Multiply by a reciprocal, use a shift-based approximation, or a dedicated divider IP/`div_gen` | `/` is supported only if the right operand is a constant power of 2, or if both are constant; `mod`/`rem` only with a constant power-of-2 right operand; `**` only with left operand 2 `[UG901 §VHDL Constructs Support Status]` |
| 19 | **Loops with dynamic bounds** | `while i < to_integer(cnt) loop ...` inside RTL to "unroll" logic | Use a `for i in 0 to g_n-1` loop with a constant bound (it unrolls at elaboration), or implement the iteration at run time with an FSM | Loops are elaboration-time constructs for synthesis; a signal-dependent bound cannot be elaborated `[IEEE 1076 / UG901 §VHDL Constructs Support Status (loop statements)]` |
| 20 | **Testbench constructs leaking into the design** | `assert false report "done" severity failure;` in RTL; `file` I/O; `std.env.stop`; `after`/`wait for` | Keep them in the testbench. In RTL use only assertions on **static conditions** | "Assertion statement: supported for static conditions only"; concurrent assertions are ignored `[UG901 §VHDL Constructs Support Status]` |
| 21 | **Two design units in one file / wrong file naming** | `mux.vhd` containing `entity mux2`, `entity mux4`, and a package | One entity + one architecture per file, file name = entity name | Vivado recompiles whole files and a file is the unit of incremental build; multi-entity files break the "one module = one file = one testbench" contract used by agent tooling `[derived]` |
| 22 | **Unconstrained ports / `std_logic_vector` without bound on a top** | `port (i_d : in std_logic_vector);` on the top entity | Give every **top-level** port an explicit range: `std_logic_vector(C_DATA_W-1 downto 0)` | Unconstrained ports are supported by synthesis (including as entity ports for sub-modules) but an unconstrained top-level port cannot be pin-planned or constrained `[UG901 §VHDL Constructs Support Status; UG1118 §Top-Level HDL Requirements]` |

### 1.2 The five rules to state to any LLM before it writes VHDL

1. Everything assigned in a clocked process becomes a register: say out loud whether
   each output is intended to be registered or combinational `[UG901 §VHDL Sequential Logic]`.
2. Every combinational process starts with default assignments to all its outputs;
   otherwise you get a latch (`Synth 8-327`) `[UG901 §Latches Reporting Example]`.
3. Sensitivity lists are not optional documentation: clock + all async controls
   `[UG901 §Flip-Flops, Registers, and Latches]`.
4. Arithmetic goes through `ieee.numeric_std`, with explicit conversions and widths.
5. No time, no `after`, no `real`, no `wait for` in RTL: the synthesizer ignores or
   rejects them `[UG901 §VHDL Constructs Support Status]`.

---

## 2. Copy-paste skeletons

All skeletons use the repository conventions described in §3 (`i_`/`o_`/`s_`/`C_`/`g_`
prefixes, `std_logic`/`std_logic_vector` ports, active-high synchronous reset
`i_rst`). They compile as VHDL-93/2002 unless stated otherwise. The two `context`
lines (`library ieee; use ...`) are repeated per file because Vivado compiles file by
file and a designer file that forgets them is the single most common elaboration error.

### 2.1 Entity + combinational architecture (selected assignment)

```vhdl
-- mux4.vhd -- 4:1 byte multiplexer, purely combinational
library ieee;
  use ieee.std_logic_1164.all;

entity mux4 is
  port (
    i_sel : in  std_logic_vector(1 downto 0);
    i_d0  : in  std_logic_vector(7 downto 0);
    i_d1  : in  std_logic_vector(7 downto 0);
    i_d2  : in  std_logic_vector(7 downto 0);
    i_d3  : in  std_logic_vector(7 downto 0);
    o_y   : out std_logic_vector(7 downto 0)
  );
end entity mux4;

architecture rtl of mux4 is
begin
  with i_sel select
    o_y <= i_d0 when "00",
           i_d1 when "01",
           i_d2 when "10",
           i_d3 when others;
end architecture rtl;
```

Equivalent process form (needed when the outputs are vectors computed differently per
branch) — note the **defaults first**:

```vhdl
  p_mux : process (i_sel, i_d0, i_d1, i_d2, i_d3) is
  begin
    o_y <= i_d0;                      -- default: prevents a latch (UG901 Synth 8-327)
    case i_sel is
      when "01"   => o_y <= i_d1;
      when "10"   => o_y <= i_d2;
      when "11"   => o_y <= i_d3;
      when others => o_y <= i_d0;
    end case;
  end process p_mux;
```

### 2.2 Register with synchronous reset (and clock enable)

```vhdl
-- reg_sync.vhd -- storage element, synchronous active-high reset
library ieee;
  use ieee.std_logic_1164.all;

entity reg_sync is
  generic (
    g_width : natural := 8
  );
  port (
    i_clk : in  std_logic;
    i_rst : in  std_logic;
    i_en  : in  std_logic;
    i_d   : in  std_logic_vector(g_width - 1 downto 0);
    o_q   : out std_logic_vector(g_width - 1 downto 0)
  );
end entity reg_sync;

architecture rtl of reg_sync is
  signal s_q : std_logic_vector(g_width - 1 downto 0) := (others => '0');
begin
  p_reg : process (i_clk) is
  begin
    if rising_edge(i_clk) then
      if i_rst = '1' then
        s_q <= (others => '0');
      elsif i_en = '1' then
        s_q <= i_d;
      end if;
    end if;
  end process p_reg;

  o_q <= s_q;
end architecture rtl;
```

Asynchronous-reset variant (only if the project requires it — it costs routing and
complicates timing):

```vhdl
  p_reg_async : process (i_clk, i_rst) is   -- async control in the sensitivity list
  begin
    if i_rst = '1' then
      s_q <= (others => '0');
    elsif rising_edge(i_clk) then
      s_q <= i_d;
    end if;
  end process p_reg_async;
```

### 2.3 Two-process FSM (recommended for LLMs: easiest to review)

```vhdl
-- ctrl_fsm.vhd -- Moore FSM, next-state (combinational) + state register
library ieee;
  use ieee.std_logic_1164.all;

entity ctrl_fsm is
  port (
    i_clk  : in  std_logic;
    i_rst  : in  std_logic;
    i_go   : in  std_logic;
    i_done : in  std_logic;
    o_busy : out std_logic;
    o_we   : out std_logic
  );
end entity ctrl_fsm;

architecture rtl of ctrl_fsm is
  type t_state is (ST_IDLE, ST_RUN, ST_DONE);
  signal s_state : t_state;
  signal s_next  : t_state;
begin
  p_state : process (i_clk) is
  begin
    if rising_edge(i_clk) then
      if i_rst = '1' then
        s_state <= ST_IDLE;
      else
        s_state <= s_next;
      end if;
    end if;
  end process p_state;

  p_next : process (s_state, i_go, i_done) is
  begin
    s_next <= s_state;          -- default assignment
    o_busy <= '0';
    o_we   <= '0';
    case s_state is
      when ST_IDLE =>
        if i_go = '1' then
          s_next <= ST_RUN;
        end if;
      when ST_RUN =>
        o_busy <= '1';
        if i_done = '1' then
          s_next <= ST_DONE;
        end if;
      when ST_DONE =>
        o_we   <= '1';
        s_next <= ST_IDLE;
      -- no "when others" needed: every value of t_state is covered. If the state is
      -- ever encoded as std_logic_vector instead of an enumeration, "when others" or
      -- the FSM_SAFE_STATE attribute becomes mandatory.
    end case;
  end process p_next;
end architecture rtl;
```

The state register must be reset so the FSM cannot power up in an illegal state; in
7-series fabrics the state encoding defaults to one-hot/sequential per the synthesis
strategy and `FSM_ENCODING` / `FSM_SAFE_STATE` attributes exist to control it
`[UG901 §Synthesis Attributes]`.

### 2.4 One-process FSM (compact; outputs are registered, so +1 clock latency)

```vhdl
architecture rtl_1p of ctrl_fsm is
  type t_state is (ST_IDLE, ST_RUN, ST_DONE);
  signal s_state : t_state := ST_IDLE;
begin
  p_fsm : process (i_clk) is
  begin
    if rising_edge(i_clk) then
      if i_rst = '1' then
        s_state <= ST_IDLE;
        o_busy  <= '0';
        o_we    <= '0';
      else
        o_busy <= '0';           -- defaults, every cycle
        o_we   <= '0';
        case s_state is
          when ST_IDLE =>
            if i_go = '1' then
              s_state <= ST_RUN;
            end if;
          when ST_RUN =>
            o_busy <= '1';
            if i_done = '1' then
              s_state <= ST_DONE;
            end if;
          when ST_DONE =>
            o_we    <= '1';
            s_state <= ST_IDLE;
        end case;              -- complete over t_state; no "when others" required
      end if;
    end if;
  end process p_fsm;
end architecture rtl_1p;
```

**Trade-off to document in the header comment:** the two-process style decodes outputs
combinationally (same-cycle `o_we`), the one-process style registers every output
(`o_we` one cycle later) and is easier to keep glitch-free. Both are legal and
synthesizable; only the latency differs.

### 2.5 Counter with enable and terminal count

```vhdl
-- counter_up.vhd
library ieee;
  use ieee.std_logic_1164.all;
  use ieee.numeric_std.all;

entity counter_up is
  generic (
    g_width : natural := 8
  );
  port (
    i_clk  : in  std_logic;
    i_rst  : in  std_logic;
    i_en   : in  std_logic;
    o_cnt  : out std_logic_vector(g_width - 1 downto 0);
    o_tick : out std_logic
  );
end entity counter_up;

architecture rtl of counter_up is
  signal s_cnt : unsigned(g_width - 1 downto 0) := (others => '0');
begin
  p_cnt : process (i_clk) is
  begin
    if rising_edge(i_clk) then
      if i_rst = '1' then
        s_cnt <= (others => '0');
      elsif i_en = '1' then
        s_cnt <= s_cnt + 1;                 -- wraps naturally at 2**g_width
      end if;
    end if;
  end process p_cnt;

  o_cnt  <= std_logic_vector(s_cnt);
  o_tick <= '1' when s_cnt = to_unsigned(2 ** g_width - 1, g_width) else '0';
end architecture rtl;
```

Keep the count value as `unsigned` internally and convert **once** at the port; this
removes a whole family of `std_logic_vector`-arithmetic errors (§1, row 9).

### 2.6 Frequency division — clock enable (preferred) and real divided clock

**Preferred: a synchronous clock enable.** One clock domain, no gated clock, no
`create_generated_clock` needed.

```vhdl
-- clk_en_gen.vhd -- one-cycle enable every g_div clocks
library ieee;
  use ieee.std_logic_1164.all;

entity clk_en_gen is
  generic (
    g_div : positive := 100        -- division ratio, >= 2
  );
  port (
    i_clk : in  std_logic;
    i_rst : in  std_logic;
    o_en  : out std_logic
  );
end entity clk_en_gen;

architecture rtl of clk_en_gen is
  signal s_cnt : integer range 0 to g_div - 1 := 0;
begin
  p_div : process (i_clk) is
  begin
    if rising_edge(i_clk) then
      if i_rst = '1' then
        s_cnt <= 0;
        o_en  <= '0';
      else
        o_en <= '0';
        if s_cnt = g_div - 1 then
          s_cnt <= 0;
          o_en  <= '1';
        else
          s_cnt <= s_cnt + 1;
        end if;
      end if;
    end if;
  end process p_div;
end architecture rtl;
```

Use it as `if rising_edge(i_clk) then if i_en_slow = '1' then ... end if; end if;`.

**If a real divided clock is unavoidable** (e.g. feeding an I/O block, an ODDR, or an
external pin):

* register the divide toggle and drive it through a global clock buffer —
  `BUFGCE`/`BUFGCTRL`/`BUFR` rather than an `and` gate `[UG949 §7 Series Device Clocking]`;
* declare the resulting clock so the timing engine knows its period:
  `create_generated_clock -name clk_div -source [get_pins u_bufg/I] -divide_by 2 [get_pins u_bufg/O]`
  `[UG903 §Generated Clocks]`;
* remember "user logic cannot multiply the master clock frequency, unlike PLL or MMCM"
  `[UG903 §Generated Clocks]` — only an MMCM/PLL (Clocking Wizard IP) can multiply.

### 2.7 Edge detector (1-cycle pulse, registered)

```vhdl
-- edge_det.vhd
library ieee;
  use ieee.std_logic_1164.all;

entity edge_det is
  port (
    i_clk  : in  std_logic;
    i_rst  : in  std_logic;
    i_sig  : in  std_logic;      -- must already be synchronous to i_clk
    o_rise : out std_logic;      -- registered, high for exactly one i_clk cycle
    o_fall : out std_logic
  );
end entity edge_det;

architecture rtl of edge_det is
  signal s_q1 : std_logic := '0';
  signal s_q2 : std_logic := '0';
begin
  p_edge : process (i_clk) is
  begin
    if rising_edge(i_clk) then
      if i_rst = '1' then
        s_q1   <= '0';
        s_q2   <= '0';
        o_rise <= '0';
        o_fall <= '0';
      else
        s_q1   <= i_sig;
        s_q2   <= s_q1;
        o_rise <= s_q1 and (not s_q2);
        o_fall <= (not s_q1) and s_q2;
      end if;
    end if;
  end process p_edge;
end architecture rtl;
```

Never feed this block with an asynchronous signal directly: synchronise first (§2.8).

### 2.8 Two-flip-flop synchroniser (with `ASYNC_REG`)

```vhdl
-- sync_2ff.vhd -- single-bit CDC synchroniser
library ieee;
  use ieee.std_logic_1164.all;

entity sync_2ff is
  port (
    i_clk   : in  std_logic;
    i_async : in  std_logic;     -- asynchronous input, same clock domain as o_sync
    o_sync  : out std_logic
  );
end entity sync_2ff;

architecture rtl of sync_2ff is
  signal s_meta : std_logic := '0';
  signal s_sync : std_logic := '0';
  attribute async_reg : string;
  attribute async_reg of s_meta : signal is "TRUE";
  attribute async_reg of s_sync : signal is "TRUE";
begin
  p_sync : process (i_clk) is
  begin
    if rising_edge(i_clk) then
      s_meta <= i_async;         -- first stage: may go metastable
      s_sync <= s_meta;          -- second stage: resolves
    end if;
  end process p_sync;

  o_sync <= s_sync;
end architecture rtl;
```

`ASYNC_REG` is a Vivado synthesis attribute that must be applied correctly for the tool
to recognise the synchroniser and to run `report_synchronizer_mtbf`; AMD provides the
`XPM_CDC` macros so the circuit is recognised without hand-coding `[UG949 §Clock Domain
Crossing]`, `[UG901 §ASYNC_REG]`. For a multi-bit bus, **never** synchronise bit by bit:
use a handshake, a gray-coded counter, or an asynchronous FIFO / `XPM_CDC` macro
`[UG949 §Clock Domain Crossing]`.

### 2.9 Synchronous FIFO (small, single clock)

For depth > ~16, dual-clock operation, or first-word-fall-through behaviour, do **not**
hand-write this: use the FIFO Generator IP or `XPM_FIFO_*` macros (§6)
`[UG949 §Clock Domain Crossing]`.

```vhdl
-- fifo_sync.vhd -- single-clock FIFO with count-based flags
library ieee;
  use ieee.std_logic_1164.all;
  use ieee.numeric_std.all;

entity fifo_sync is
  generic (
    g_width : natural := 8;
    g_depth : natural := 16          -- must be a power of two
  );
  port (
    i_clk   : in  std_logic;
    i_rst   : in  std_logic;
    i_wr    : in  std_logic;
    i_rd    : in  std_logic;
    i_data  : in  std_logic_vector(g_width - 1 downto 0);
    o_data  : out std_logic_vector(g_width - 1 downto 0);
    o_full  : out std_logic;
    o_empty : out std_logic
  );
end entity fifo_sync;

architecture rtl of fifo_sync is
  function log2_ceil (n : positive) return natural is
    variable v_p : natural := 1;
    variable v_c : natural := 0;
  begin
    while v_p < n loop
      v_p := v_p * 2;
      v_c := v_c + 1;
    end loop;
    return v_c;
  end function log2_ceil;

  constant C_AW : natural := log2_ceil(g_depth);

  type t_mem is array (0 to g_depth - 1) of std_logic_vector(g_width - 1 downto 0);

  signal s_mem  : t_mem;
  signal s_wptr : unsigned(C_AW - 1 downto 0)  := (others => '0');
  signal s_rptr : unsigned(C_AW - 1 downto 0)  := (others => '0');
  signal s_cnt  : unsigned(C_AW downto 0)      := (others => '0');
  signal s_full : std_logic;
  signal s_empty: std_logic;
begin
  s_full  <= '1' when to_integer(s_cnt) = g_depth else '0';
  s_empty <= '1' when to_integer(s_cnt) = 0       else '0';

  o_full  <= s_full;
  o_empty <= s_empty;
  o_data  <= s_mem(to_integer(s_rptr));   -- asynchronous read; see note below

  -- ONE process only: the memory array must never be written from two processes
  p_fifo : process (i_clk) is
    variable v_do_wr : boolean;
    variable v_do_rd : boolean;
  begin
    if rising_edge(i_clk) then
      if i_rst = '1' then
        s_wptr <= (others => '0');
        s_rptr <= (others => '0');
        s_cnt  <= (others => '0');
      else
        v_do_wr := (i_wr = '1') and (s_full  = '0');
        v_do_rd := (i_rd = '1') and (s_empty = '0');

        if v_do_wr then
          s_mem(to_integer(s_wptr)) <= i_data;
          s_wptr <= s_wptr + 1;
        end if;

        if v_do_rd then
          s_rptr <= s_rptr + 1;
        end if;

        if v_do_wr and not v_do_rd then
          s_cnt <= s_cnt + 1;
        elsif v_do_rd and not v_do_wr then
          s_cnt <= s_cnt - 1;
        end if;
      end if;
    end if;
  end process p_fifo;
end architecture rtl;
```

Documented limitations to keep in the header comment: asynchronous read (add a read
register, or let the tool infer a block RAM with `DOA_REG`), no almost-full/empty, no
data-count output, single clock only.

### 2.10 Wide multiplexer (case form, no latch)

```vhdl
  p_mux : process (i_sel, i_d) is
  begin
    o_y <= (others => '0');                 -- default
    case i_sel is
      when 0      => o_y <= i_d(0);
      when 1      => o_y <= i_d(1);
      when 2      => o_y <= i_d(2);
      when others => o_y <= i_d(3);
    end case;
  end process p_mux;
```

For a large mux (many sources), prefer a one-hot selection with OR-reduction, or let
synthesis build the MUXF7/MUXF8 tree — a deep binary `case` costs logic levels and is
often the critical path (§5).

### 2.11 Generic + `for-generate` (constant bounds only)

```vhdl
-- bitpipe.vhd : one pipeline stage
library ieee;
  use ieee.std_logic_1164.all;

entity bitpipe is
  port (
    i_clk : in  std_logic;
    i_d   : in  std_logic;
    o_q   : out std_logic
  );
end entity bitpipe;

architecture rtl of bitpipe is
begin
  p_pipe : process (i_clk) is
  begin
    if rising_edge(i_clk) then
      o_q <= i_d;
    end if;
  end process p_pipe;
end architecture rtl;
```

```vhdl
-- delay_line.vhd : g_stages instances of bitpipe, chained
library ieee;
  use ieee.std_logic_1164.all;

entity delay_line is
  generic (
    g_stages : positive := 4
  );
  port (
    i_clk : in  std_logic;
    i_d   : in  std_logic;
    o_q   : out std_logic
  );
end entity delay_line;

architecture rtl of delay_line is
  signal s_pipe : std_logic_vector(g_stages downto 0);
begin
  s_pipe(0) <= i_d;

  g_stage : for i in 0 to g_stages - 1 generate   -- constant bounds (UG901)
    u_bitpipe : entity work.bitpipe(rtl)
      port map (
        i_clk => i_clk,
        i_d   => s_pipe(i),
        o_q   => s_pipe(i + 1)
      );
  end generate g_stage;

  o_q <= s_pipe(g_stages);
end architecture rtl;
```

Use direct entity instantiation (`entity work.bitpipe(rtl)`) rather than
component + configuration: it needs no component declaration, keeps the port list in
one place, and gives an elaboration-time error on a mismatch instead of a silent
binding to a stale component `[UG901 §VHDL Component Instantiation]` `[derived]`.

### 2.12 Package with shared constants, subtypes and helper functions

```vhdl
-- proj_pkg.vhd : project-wide definitions
library ieee;
  use ieee.std_logic_1164.all;

package proj_pkg is
  constant C_DATA_W : natural := 32;
  constant C_ADDR_W : natural := 10;

  subtype t_word is std_logic_vector(C_DATA_W - 1 downto 0);
  subtype t_addr is std_logic_vector(C_ADDR_W - 1 downto 0);

  function log2_ceil (n : positive) return natural;
  function slv_to_int (v : std_logic_vector) return integer;
end package proj_pkg;

package body proj_pkg is
  function log2_ceil (n : positive) return natural is
    variable v_p : natural := 1;
    variable v_c : natural := 0;
  begin
    while v_p < n loop
      v_p := v_p * 2;
      v_c := v_c + 1;
    end loop;
    return v_c;
  end function log2_ceil;

  function slv_to_int (v : std_logic_vector) return integer is
    variable v_res : integer := 0;
  begin
    for i in v'range loop
      v_res := v_res * 2;
      if v(i) = '1' then
        v_res := v_res + 1;
      end if;
    end loop;
    return v_res;
  end function slv_to_int;
end package body proj_pkg;
```

Packages may contain "types and subtypes, constants, functions and procedures,
component declarations"; a package declaration plus a package body is required
`[UG901 §Defining Your Own VHDL Packages]`, and predefined `STD`/`IEEE` libraries are
pre-compiled and need no user compilation `[UG901 §VHDL Predefined Packages]`.
`log2_ceil` above is an **elaboration-time (constant) function**: it is legal only for
constant calculations such as a range bound, exactly the use UG901 documents for
functions and procedures `[UG901 §VHDL Functions and Procedures]`; a function whose
loop bound depends on a signal would not be synthesizable.
**Caveat for LLM workflows:** a package edit invalidates everything that `use`s it, so
keep constants that change per build (widths of interfaces, addresses) in
generics, and keep only truly project-wide items in the package `[derived]`.

### 2.13 Conversion functions package

```vhdl
library ieee;
  use ieee.std_logic_1164.all;
  use ieee.numeric_std.all;

package conv_pkg is
  function slv_to_nat (v : std_logic_vector) return natural;
  function nat_to_slv (v : natural; w : positive) return std_logic_vector;
  function onehot_to_bin (v : std_logic_vector) return std_logic_vector;
end package conv_pkg;

package body conv_pkg is
  function slv_to_nat (v : std_logic_vector) return natural is
  begin
    return to_integer(unsigned(v));
  end function slv_to_nat;

  function nat_to_slv (v : natural; w : positive) return std_logic_vector is
  begin
    return std_logic_vector(to_unsigned(v, w));
  end function nat_to_slv;

  function onehot_to_bin (v : std_logic_vector) return std_logic_vector is
    variable v_r : std_logic_vector(v'length - 1 downto 0) := (others => '0');
  begin
    for i in v'range loop
      if v(i) = '1' then
        v_r := v_r or std_logic_vector(to_unsigned(i, v'length));
      end if;
    end loop;
    return v_r;
  end function onehot_to_bin;
end package body conv_pkg;
```

Always convert at the boundary of a computation (`unsigned`/`signed` in, conversions at
the ports) rather than sprinkling casts through an architecture.

### 2.14 Top-level wrapper with `i_*` / `o_*` ports

```vhdl
-- top.vhd : pin-level wrapper, no logic other than instantiation
library ieee;
  use ieee.std_logic_1164.all;
  use work.proj_pkg.all;

entity top is
  generic (
    g_width : natural := C_DATA_W
  );
  port (
    i_clk : in  std_logic;                          -- board clock (create_clock in XDC)
    i_rst : in  std_logic;                          -- button / reset source
    i_go  : in  std_logic;
    i_d   : in  std_logic_vector(g_width - 1 downto 0);
    o_q   : out std_logic_vector(g_width - 1 downto 0);
    o_we  : out std_logic
  );
end entity top;

architecture rtl of top is
  signal s_en  : std_logic;
  signal s_fsm_we : std_logic;
begin
  u_clk_en : entity work.clk_en_gen(rtl)
    generic map (
      g_div => 100
    )
    port map (
      i_clk => i_clk,
      i_rst => i_rst,
      o_en  => s_en
    );

  u_fsm : entity work.ctrl_fsm(rtl)
    port map (
      i_clk  => i_clk,
      i_rst  => i_rst,
      i_go   => i_go,
      i_done => s_en,
      o_busy => open,          -- unused outputs: use open, never a dangling named map
      o_we   => s_fsm_we
    );

  o_we <= s_fsm_we;
  o_q  <= i_d;                 -- replace with the real datapath
end architecture rtl;
```

`open` for unused outputs, `others => '0'` for unused inputs of constant value, and no
port left unconnected without a comment `[derived]`.

---

## 3. Naming, documentation and file-splitting conventions

### 3.1 Recommended default (and why)

**Default: keep the repository convention `i_` / `o_` / `s_` / `C_` / `G_` / `p_`.**

| Prefix | Object | Example |
|---|---|---|
| `i_` | input port | `i_clk`, `i_rst`, `i_data` |
| `o_` | output port | `o_data`, `o_valid` |
| `io_` | bidirectional port | `io_sda` |
| `s_` | internal signal | `s_cnt`, `s_state` |
| `C_` | constant (package or architecture) | `C_DATA_W` |
| `G_` | generic | `g_width`, `g_depth` (lowercase after the prefix, as in the repo's existing code) |
| `p_` | process label | `p_reg`, `p_next` |

Justification, in order of weight:

1. **It is already the project convention** (see the repo's own VHDL/CoCoTb notes).
   Consistency beats local perfection: a second style inside the same repo costs more
   than either style chosen alone.
2. **It survives copy-paste into a testbench.** CoCoTb/Python drives ports by name
   (`dut.i_clk`, `dut.o_data`); a direction prefix makes a generated testbench correct
   on the first try and makes an LLM-written testbench self-checking.
3. **It is mechanically checkable.** `o_` assigned outside a clocked process, `i_`
   driven internally, an `s_` signal appearing in a port map as an input — all are
   grep-able mistakes.
4. **It matches the IP packager's clock-interface inference**, which accepts names of
   the form `[*_]clk`, `[*_]clkin`, `[*_]clock[_*]`, `[*_]aclk`, `[*_]aclkin`
   (case-insensitive, `[_*]` = optional suffix) `[UG1118 §Inferring Clock Interfaces]`.
   `i_clk` matches `[*_]clk`, so clock interfaces are inferred automatically when the
   block is packaged as IP.

Alternatives and when to take them: the industry-neutral style (lowercase ports with
no direction prefix, e.g. `clk`, `rst_n`, `data_out`) is more common in published IP and
in vendor documentation, and **`_n` suffix for active-low signals** is worth adopting
whichever prefix scheme you use (never `rst` meaning active-low). If a project must
integrate vendor sources, keep the vendor files untouched and apply the prefix scheme
only to the project's own files, with a wrapper if needed.

Hard rules independent of the scheme: ports are `std_logic` / `std_logic_vector` only
(VHDL top-level ports must be `std_logic`/`std_logic_vector` "to ensure the custom IP
simulates properly when using VHDL"; OOC synthesis converts the netlist ports to those
types anyway) `[UG1118 §Top-Level HDL Requirements]`; no HDL language keywords as
identifiers `[UG1118 §Top-Level HDL Requirements]`; constant names never hold a value
that changes with a build option (generics do that).

### 3.2 Documentation block for every file

A header comment that an LLM can re-read mechanically — the tabular part matters more
than the prose, because it is what the next agent parses:

```vhdl
--------------------------------------------------------------------------------
-- Module      : fifo_sync
-- File        : src/hdl/fifo/fifo_sync.vhd
-- Description : single-clock FIFO, count-based full/empty flags
-- Clock       : i_clk only (single clock domain)
-- Reset       : i_rst, synchronous, active-high, asserted for >= 2 i_clk cycles
-- Latency     : data visible on o_data the cycle after i_wr (asynchronous read)
-- Generics    : g_width (data width), g_depth (entries, power of two)
-- Ports       : i_wr  - write enable, ignored when o_full = '1'
--               i_rd  - read enable, ignored when o_empty = '1'
-- Constraints : none (internal clock only); see src/constraints/top_timing.xdc
-- Testbench   : tb/fifo/testbench_fifo_sync.py  (make SIM=ghdl)
-- Status      : verified in simulation only, not on hardware
-- Revision    : 2026-09-17  v0.1  created
--------------------------------------------------------------------------------
```

Rules that make documentation useful to a re-reading agent `[derived]`:

* State the **clock domain(s)** and the **reset** polarity/synchronism explicitly —
  most integration bugs are domain or polarity mismatches.
* State **latency** and **throughput** in cycles (the FSM two-process/one-process
  difference in §2.3/2.4 is exactly this).
* Name the **testbench** and the **constraints file** that go with the module.
* Record the **status**: simulation-only / implemented / validated on hardware. An
  agent must never present a simulated-only module as validated.
* One obligation per line, no marketing adjectives.

### 3.3 File-splitting rules

| Rule | Rationale |
|---|---|
| One entity + one architecture per file, file name = entity name (`.vhd`) | The file is the recompilation unit; mismatched names break incremental builds and confuse tooling |
| ≤ ~300–400 lines per file | Beyond that, an LLM's attention over the file degrades and the reviewer cannot hold the module in mind |
| One clock domain per file | Same reason: cross-domain logic (synchronisers, CDC FIFOs) deserves its own tiny, heavily commented file |
| Separate pure-combinational functions from storage | Makes the pipelining stage count visible and testable |
| Shared types/constants only in a `*_pkg.vhd` | A package change invalidates everything that uses it; keep it small and stable |
| Constraints in their own files: `*_timing.xdc`, `*_io.xdc`, `*_debug.xdc` | Vivado recommends "separate timing constraints and physical constraints into two distinct files" and per-module constraint files `[UG903 §Organizing Your Constraints]` |
| Testbench per module, in `tb/<module>/`, generated by the same tool as the RTL | Keeps the simulation collateral next to the unit under test |
| Never two entities with the same name in different libraries of the same project | Ambiguous binding; Vivado resolves to the default library `[UG901 §VHDL Constructs Support Status (configuration)]` |

Recommended tree (matches the existing repo layout):

```
src/hdl/            *.vhd             one file per entity
src/hdl/<function>/ sub-directories per functional block, top at src/hdl/top.vhd
src/pkg/            *_pkg.vhd         shared constants / types / conversion functions
src/constraints/    *_timing.xdc, *_io.xdc, *_debug.xdc
tb/<module>/        testbench_*.py + Makefile (CoCoTb)
scripts/            *.tcl             project creation / build / report harvesting
docs/               interface tables, this note family
```

---

## 4. XDC constraints

### 4.1 What an XDC file is

"XDCs combine the industry-standard SDCs version 1.9 with AMD proprietary physical
constraints. XDC constraints have these properties: they act as Tcl commands, not
simple strings; the Vivado Tcl interpreter processes them like any other Tcl command;
Vivado reads and parses them sequentially, the same as other Tcl commands."
`[UG903 §About XDC Constraints]`

Consequences for an LLM authoring XDC:

* order matters (a constraint that is later overwritten wins, and `set_clock_groups`
  applies to clocks that already exist) `[UG903 §About XDC Constraints]`;
* any Tcl is legal (variables, `if`, `foreach`) — but keep it declarative for review;
* the valid command set is fixed: timing (`create_clock`, `create_generated_clock`,
  `set_clock_groups`, `set_false_path`, `set_input_delay`, `set_output_delay`,
  `set_max_delay`, `set_min_delay`, `set_multicycle_path`, `set_case_analysis`,
  `set_clock_uncertainty`, `set_propagated_clock`, `group_path`, …), physical
  (`create_pblock`, `add_cells_to_pblock`, `resize_pblock`, `create_macro`,
  `set_package_pin_val`), general purpose (`set_property`, `get_property`,
  `create_property`, `current_instance`, `create_waiver`), debug (`create_debug_core`,
  `create_debug_port`, `connect_debug_port`), power, and netlist constraints
  `[UG903 §Valid Commands in an XDC File]`.

Physical constraints are used only by implementation ("optimization, placement and
routing"), which is why pin/IOSTANDARD assignments are harmless during synthesis but
mandatory for bitstream generation `[UG949 §Design Constraints]`.

### 4.2 Command reference (what to write, and the traps)

| Command | Canonical form | Traps |
|---|---|---|
| `create_clock` | `create_clock -name sys_clk -period 10.000 [get_ports i_clk]` | Define it on the **input port**, not on the clock-buffer output `[UG903 §Primary Clocks Examples]`. Objects may be "clock source ports, pins or nets" `[UG835 §create_clock]`. For a differential input, create the clock on the **positive** pin only, otherwise you get unrealistic CDC paths `[UG903 §Primary Clocks Examples]`. `-waveform {rise fall}` must contain an **even** number of edges, nanoseconds, first value = first rising edge; default 50 % duty, 0 phase `[UG903 §About Clocks]`. Do **not** use `create_clock` where `create_generated_clock` is meant: the generated clock would not inherit insertion delay/jitter and timing is computed wrongly `[UG835 §create_clock]` |
| `create_generated_clock` | `create_generated_clock -name clk_div -source [get_pins u_div/C] -divide_by 2 [get_pins u_bufg/O]` | Must be attached to a netlist object, preferably the **root pin of the clock tree**; `-source` accepts only a **pin or port**, never a clock object `[UG903 §User Defined Generated Clocks]`. User logic can only **divide**; multiplication needs an MMCM/PLL `[UG903 §Generated Clocks]`. MMCM/PLL outputs are auto-derived, so most designs need no manual generated clock at all `[UG903 §Generated Clocks]` |
| `set_input_delay` | `set_input_delay -clock sys_clk -max 2.0 [get_ports i_d]` + a matching `-min` | The delay is the **external** board delay, in ns, relative to a clock edge (or `-reference_pin`) `[UG835 §set_input_delay]`. Provide **both** `-max` and `-min`, otherwise the path is excluded from either setup or hold analysis (see `partial_input_delay` in §4.5) `[UG906 §Check Timing Section]` |
| `set_output_delay` | `set_output_delay -clock sys_clk -max 2.0 [get_ports o_q]` + matching `-min` | Same symmetry rule; the reference clock is normally the board clock, or a virtual clock when the internal clock has a different period/phase `[UG903 §Output Delays]` |
| `set_false_path` | `set_false_path -from [get_clocks CLKA] -to [get_clocks CLKB]` | Valid startpoints: clock object, clock pin of a sequential element, input/inout port; valid endpoints: clock object, output/input port, data pin of a sequential element `[UG903 §False Paths]`. It is **directional** — a single command does not cut the return path `[UG903 §False Paths]`. Avoid `-through` alone: it removes any path crossing the pin, and `-through A -through B` ≠ `-through B -through A` `[UG903 §False Paths]`. Prefer `set_clock_groups` for two asynchronous domains `[UG903 §False Paths]`; use `set_multicycle_path` (not a false path) when the path must still be timed `[UG903 §False Paths]` |
| `set_clock_groups` | `set_clock_groups -name async_a_b -asynchronous -group [get_clocks -include_generated_clocks clkA] -group [get_clocks -include_generated_clocks clkB]` | `-logically_exclusive`, `-physically_exclusive`, `-asynchronous` are mutually exclusive `[UG835 §set_clock_groups]`. With a single `-group`, that group is asynchronous to *all other* clocks in the design, but not to itself `[UG835 §set_clock_groups]`. `get_clocks -include_generated_clocks` is an SDC extension and is the robust way to catch auto-derived names `[UG903 §Creating Asynchronous Clock Groups]` |
| `set_max_delay` | `set_max_delay -datapath_only -from [get_pins u_a/C] -to [get_pins u_b/D] 4.0` | Must be assigned through at least one `-from`/`-through`/`-to`; a general `-to` is overwritten by a more specific path `[UG835 §set_max_delay]`. `set_min_delay` must not be larger than the max on the same path, otherwise the first constraint is discarded and set to 0 `[UG835 §set_max_delay]`. A `set_input_delay`/`set_output_delay` at a port **consumes part of** the max-delay budget of that path `[UG835 §set_max_delay, §set_input_delay]`. `-datapath_only` removes clock skew/jitter from the calculation — the usual companion of a CDC false path |
| `set_property PACKAGE_PIN / IOSTANDARD` | `set_property -dict {PACKAGE_PIN W5 IOSTANDARD LVCMOS33} [get_ports i_clk]` | Assign on the **port**; properties apply to port objects unless stated otherwise `[UG903 §I/O Constraints]`. Common I/O properties: `IOSTANDARD`, `DRIVE`, `SLEW`, `IN_TERM`, `DIFF_TERM`, `KEEPER`, `PULLTYPE`, `IOB`, `IOB_TRI_REG` `[UG903 §I/O Constraints]`. `IOB TRUE` on a port or a register (register wins in case of conflict) — Vivado accepts only TRUE/FALSE (`FORCE` → TRUE, `AUTO` ignored) and raises a **critical warning** instead of an error if it cannot be honoured `[UG903 §I/O Constraints]` |
| `set_property CLOCK_DEDICATED_ROUTE` | `set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets i_clk_ibuf]` | Advanced, dangerous: allows the clock to reach a BUFG/MMCM through general routing when the input pin is not clock-capable (CCIO). "Use this only as a last resort when package pin assignments are fixed"; routing becomes suboptimal/unpredictable without `FIXED_ROUTE` `[UG903 §CLOCK_DEDICATED_ROUTE]` |

### 4.3 XDC by flow stage (synthesis vs implementation)

| Stage | What to put there | Source |
|---|---|---|
| Synthesis (`constrs_1`, used in synthesis) | `create_clock` / `create_generated_clock`, clock uncertainty, timing exceptions that drive optimisation, synthesis attributes (`ASYNC_REG`, `KEEP_HIERARCHY`, `RAM_STYLE`, …) | "Synthesis uses four categories of constraints: RTL attributes, timing constraints, physical and configuration constraints, elaborated design constraints" `[UG903 §Creating Synthesis Constraints]` |
| Implementation (XDC marked for implementation) | pin locations, IOSTANDARD, Pblocks, complete I/O delays, false paths / multicycle paths / max-min delays | After loading the netlist: "add missing constraints such as input and output delay; add timing exceptions such as false paths, multicycle paths, and min/max delay" `[UG903 §Creating Implementation Constraints]` |
| Both | the clock definitions (one file), documented as such | "You can reuse the same base constraints from synthesis and create a second XDC file for new constraints specific to implementation" `[UG903 §Creating Implementation Constraints]` |

Practical file set for an agent-generated project:

```
src/constraints/clocks.xdc      # create_clock + generated clocks  (synthesis + impl)
src/constraints/timing.xdc      # I/O delays, exceptions, uncertainty (impl)
src/constraints/io.xdc          # PACKAGE_PIN + IOSTANDARD           (impl)
src/constraints/debug.xdc       # mark_debug / ILA properties        (impl)
```

UG903 explicitly recommends separating timing from physical constraints and keeping
module-specific constraints in their own file `[UG903 §Organizing Your Constraints]`.
Your own constraint set can be dumped for review with `write_xdc` (optionally
`-type timing|physical|waiver`) in the order the tool read them
`[UG903 §Organizing Your Constraints]`.

### 4.4 A minimal XDC that lets synthesis and implementation finish

Four cases, in order of preference.

**Case A — the design has a top-level clock port (the normal case).**

```tcl
## clocks.xdc
create_clock -name sys_clk -period 10.000 [get_ports i_clk]

## timing.xdc (implementation)
set_input_delay  -clock sys_clk -max 2.000 [get_ports i_d]
set_input_delay  -clock sys_clk -min 0.500 [get_ports i_d]
set_output_delay -clock sys_clk -max 2.000 [get_ports o_q]
set_output_delay -clock sys_clk -min 0.500 [get_ports o_q]
```

10.000 ns = 100 MHz; this is the shortest XDC that yields meaningful timing results and
is enough for synthesis and implementation to complete.

**Case B — no external I/O, but a real clock net exists inside the design.** Typical for
a PL-only block that will later be dropped inside a block design. Create the clock on
the net or pin that is the clock-tree source, and name it explicitly:

```tcl
## clocks.xdc  (design instantiated inside a larger design)
create_clock -name clk_pl -period 10.000 [get_nets u_bufg/clk_out]
```

`create_clock` accepts nets as objects `[UG835 §create_clock]`. If instead the clock
comes from the PS (Zynq), do not invent it: instantiate the PS7 block (`processing_system7`)
or the block design, and the PS clocks are constrained by the generated IP
constraints — hand-adding `create_clock` on an `FCLK_CLK0` pin afterwards creates a
second, competing definition.

**Case C — the design has neither a clock nor I/O (pure combinational netlist).**
Nothing can be timed: every path is driven by constants or by a primary input that has
no clock. Implementation completes and `report_timing_summary` legitimately reports no
timing paths. Do **not** fabricate a `create_clock` on a signal that is not a clock —
it makes the Check Timing report lie. To make such a block testable, add a real clock
port (or wrap it) rather than constraining a data signal.

**Case D — the clock enters on a pin that is not clock-capable.** Vivado cannot route it
on dedicated clock resources. Verify the pin against the package (`get_package_pins`,
UG475/UG471 for CCIO pins) before resorting to:

```tcl
set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets clk_in_ibuf]
```

which is explicitly documented as a last resort with unpredictable results
`[UG903 §CLOCK_DEDICATED_ROUTE]`.

**When the tool complains about clocks.** The visible symptoms and their real causes
(from the Check Timing and Unconstrained Paths sections of the timing summary):

| Symptom (report) | Check name | Cause / fix |
|---|---|---|
| Clock pins with no timing clock | `no_clock` | No `create_clock` on the source port/pin, or the clock is driven by a constant `[UG906 §Check Timing Section]` |
| Internal endpoints with no requirement | `unconstrained_internal_endpoints` | Usually a consequence of `no_clock`; sign-off requires this count to be **zero** `[UG949 §No Clock and Unconstrained Internal Endpoints]` |
| Input ports without delay | `no_input_delay` / `partial_input_delay` | Missing `-min` or `-max` input delay: the path is silently excluded from setup or hold analysis `[UG906 §Check Timing Section]` |
| Output ports without delay | `no_output_delay` / `partial_output_delay` | Same, on outputs `[UG906 §Check Timing Section]` |
| Clock pin reached by more than one clock | `multiple_clock` | A multiplexed clock tree; only one clock can drive it at a time `[UG906 §Check Timing Section]` |
| Generated clock whose master is elsewhere | `generated_clocks` | A disabled timing arc between master and generated source `[UG906 §Check Timing Section]` |
| Combinational loops | `loops` / `latch_loops` | Broken automatically for analysis, but fix the RTL `[UG906 §Check Timing Section]` |
| Paths listed but not timed | *Unconstrained Paths* section | Paths "not timed because of missing timing constraints", grouped per clock pair; `NONE` appears when no clock is associated `[UG906 §Unconstrained Paths Section]` |

The corresponding Tcl entry point is `check_timing` (also available as
*Reports → Timing → Check Timing*), with `-cells` scoping only from the Tcl console
`[UG906 §Check Timing Section]`.

---

## 5. Timing closure in practice

### 5.1 Reading the numbers

The Timing Summary report has three areas — Setup (max delay), Hold (min delay), Pulse
Width (pin switching limits) — summarised in the *Design Timing Summary* section, which
"aggregates results from all other sections into a single view" and should be reviewed
after implementation `[UG906 §Design Timing Summary Section]`.

| Acronym | Meaning | How to use it |
|---|---|---|
| **WNS** | Worst Negative Slack, setup | "Focus on worst negative slack (WNS) of each clock as the main way to improve total negative slack (TNS)" `[UG949 §Timing Closure]`. WNS ≥ 0 on every clock is the pass/fail criterion for setup |
| **TNS** | Total Negative Slack (sum of all setup violations) | Driving WNS to 0 usually fixes TNS; a large TNS with a small WNS means many similar paths (usually one RTL construct repeated) `[UG949 §Timing Closure]` |
| **WHS** | Worst Hold Slack | "Review large worst hold slack (WHS) violations (< -1 ns) to identify missing or inappropriate constraints" — a big hold violation is a constraint bug, not a place-and-route problem `[UG949 §Timing Closure]` |
| **THS** | Total Hold Slack | Reported alongside WHS; large pre-route WHS/THS must be reduced because hold fixing steals routing resources from Fmax `[UG1292 §Resolving Hold Violations Techniques]` |
| **WPWS / TPWS** | Worst / total pulse-width slack | Clock duty-cycle and pin-switching checks; failures usually mean a clock pin not driven by a proper clock buffer `[UG906 §Design Timing Summary Section]` |

Because synthesis uses *estimated* net delays, timing after synthesis is indicative
only: "to get the final timing results, run implementation and then check the Report
Timing Summary" `[UG949 §Timing Closure]`. Also: "the tools do not try to further
improve timing (additional margin) after timing is met" `[UG949 §Timing Closure]` — a
design that just barely meets timing has no headroom for later changes.

### 5.2 Why 100 MHz closes easily on a 7-series part

* 100 MHz is a **10 ns** period. The dominant costs on a 7-series device are the number
  of **logic levels** (LUT + carry + MUXF per level, tens to low hundreds of ps each)
  and the routing delay; register clock-to-Q and setup are small fractions of 10 ns.
* The methodology's own lever is the **logic-level distribution versus the target
  period**: the design analysis report lists logic levels per clock domain and you must
  "weigh the logic level distribution against the requirement — the lower the
  requirement, the fewer logic levels are allowed", with review thresholds such as
  "all paths with 8 logic levels or more" for a given clock `[UG1292 §Finding Setup
  Timing Path Characteristics in the Reports]`. In other words the tool itself
  quantifies "is this domain too deep for its period".
* Vivado's `report_qor_assessment` performs "conservative logic-level assessments based
  on a target Fmax" and scores the design 1–5 (5 = will meet timing) `[UG1292 §QoR
  Assessment Report Overview]`.
* `[derived]` Consequence for an agent: at 100 MHz on a -1 speed grade, a datapath with
  roughly ≤ 10 LUT levels and no congestion is normally comfortable; at 200–300 MHz the
  same datapath needs explicit pipelining. The practical failure mode of a "100 MHz
  design that fails" is almost never logic depth — it is a **constraint** error
  (undefined clock, unreferenced clock domain, missing clock groups between asynchronous
  domains, unrealistic I/O delays) or **congestion** from over-utilised fabric. Check
  the constraint reports first (§4.4), then the logic levels.

### 5.3 The ten highest-yield actions when timing fails

Ordered as the methodology recommends: constraints first, then structure, then tool
options, then implementation iterations `[UG1292]`, `[UG949 §Timing Closure]`.

| # | Action | Concrete command / change | Source |
|---|---|---|---|
| 1 | **Fix the constraints before touching RTL** | add `set_clock_groups` between independent clocks, `set_false_path` on true CDC and static paths, complete `-min/-max` I/O delays, remove over-constraining | `[UG903 §False Paths, §Creating Asynchronous Clock Groups]`; "over-constraining or under-constraining your design makes timing closure difficult" `[UG949 §Design Constraints]` |
| 2 | **Pipeline the long paths** | insert register stages on the paths flagged by `report_design_analysis` — "identifying and improving the longest paths after synthesis or after `opt_design` … has the biggest impact on QoR" | `[UG1292 §Reducing Logic Levels Techniques]` |
| 3 | **Retiming** | let synthesis move registers across logic: `RETIMING_FORWARD` / `RETIMING_BACKWARD` attributes, or the `-retiming` option of `synth_design` | `[UG901 §RETIMING_FORWARD, §RETIMING_BACKWARD]` |
| 4 | **Reduce logic levels on macro-primitive paths** | enable optional DSP/RAMB/URAM output registers (`set_property -dict {DOA_REG 1 DOB_REG 1} [get_cells …]`) as an evaluation, then add real pipeline registers | `[UG1292 §Optimizing Paths with Dedicated Blocks and Macro Primitives]` |
| 5 | **Reduce congestion / lower utilisation** | keep device or SLR utilisation below ~70–80 %; avoid simultaneous LUT > 80 % and DSP/RAMB > 80 %; `report_design_analysis -congestion` | `[UG1292 §Reducing Congestion Techniques]` |
| 6 | **Physical optimisation** | `phys_opt_design` in Explore/AggressiveExplore after place; run it after route for small setup violations (> -0.200 ns) | `[UG1292 §Pre-Routing, §Post-Routing]` |
| 7 | **Try placement/route directives and strategies (up to ~10)** | place directives (`AltSpreadLogic*`, `SSI_Spread*`), congestion strategies, ML strategies from `report_qor_suggestions` | `[UG1292 §Trying Alternative Implementation Flows]` |
| 8 | **Multicycle path where the data rate allows it** | `set_multicycle_path -from [get_pins REGA/C] -to [get_pins REGB/D] -setup 3` **and** the matching `-hold 2` | `[UG1292 §Avoiding Positive Hold Requirements]` — always constrain the endpoint **pin**, not the cell, and always adjust hold on the same path |
| 9 | **Improve the clocking** | remove LUT/buffer chains in clock paths, avoid cascaded clock buffers, use `CLOCK_DELAY_GROUP` for matched synchronous clocks, `CLOCK_LOW_FANOUT` for small clock nets, place MMCM/PLL near the loads | `[UG1292 §Improving Clock Skew Techniques]` |
| 10 | **Change the target: frequency, device, speed grade, or over-constrain slightly** | lower the clock period requirement to a realistic value, or over-constrain critical clocks by ≤ 0.500 ns with `set_clock_uncertainty` during place/phys_opt; `group_path -weight` to prioritise a clock | `[UG1292 §Trying Alternative Implementation Flows]` |

Also worth knowing: `group_path -weight` changes optimiser priorities;
`set_property CLOCK_BUFFER_TYPE BUFG [get_nets <hf_net>]` promotes a high-fanout net to
a global clock route; reducing control sets (`report_qor_assessment` guideline ~7.5 %)
removes many small delays; and the **Intelligent Design Run (IDR)** automates the
loop with `report_qor_suggestions` + ML strategies + incremental compile
`[UG1292 §Introduction, §Reducing Congestion Techniques]`.

The methodology order to keep an agent honest: review after each implementation step
(`report_timing_summary`, `report_methodology`, `report_qor_assessment`), fix at the
earliest stage that shows the problem, and iterate on **RTL, constraints, and tool
options** — not on the timing report `[UG1292 §Time Baselines]`, `[UG949 §Timing
Closure]`.

---

## 6. IP and integration

### 6.1 Generating catalog IP from Tcl

Canonical non-interactive flow (`create_ip` creates an `.xci` and adds it to the source
set; the IP must still be instantiated in the HDL) `[UG835 §create_ip]`:

```tcl
## 1) instantiate the IP core from the catalog
create_ip -name fifo_generator -vendor xilinx.com -library ip -version 13.2 \
          -module_name u_fifo

## 2) configure it — check parameter names first, they are IP-version specific
report_property [get_ips u_fifo]                      # discover CONFIG.* names
set_property -dict [list \
  CONFIG.Fifo_Implementation {Independent_Clocks_Block_RAM} \
  CONFIG.Input_Data_Width   {32} \
  CONFIG.Input_Depth        {1024} \
  CONFIG.Output_Data_Width  {32} \
] [get_ips u_fifo]

## 3) generate the output products (netlist, instantiation template, sim model)
generate_target all [get_ips u_fifo]
```

`generate_target all` generates "all targets for the specified IP or file, except the
example project"; the available targets are in the `SUPPORTED_TARGETS` property and can
be listed with `list_targets`; standard targets are the instantiation template,
synthesis netlist and simulation netlist `[UG835 §generate_target]`.

Additional commands that belong to the same workflow: `synth_ip [get_ips …]` (OOC
synthesis), `open_example_project`, `create_ip -vlnv …` (alternative to
vendor/library/name/version), and `import_ip` to read an existing `.xci`/`.xco`
`[UG835 §create_ip]`.

**Rule for agents:** never guess `CONFIG.*` parameter names. Discover them with
`report_property`/`list_property`, or generate the IP in the GUI (`write_project_tcl`
dumps the equivalent Tcl afterwards). Parameter names change between IP versions and an
unknown property is silently a no-op in some flows, a fatal error in others.

Common catalog IP for a small 7-series/Zynq project: `clk_wiz` (MMCM/PLL, clock enable &
reset, `create_generated_clock`-free clocking), `fifo_generator`, `ila`/`system_ila`
(debug, §6.5), `blk_mem_gen`, `axi_gpio`/`axi_bram_ctrl`/`axi_interconnect` (Zynq PS-PL
paths), `mig_7series`, `div_gen`, `cordic`.

### 6.2 What "packaged IP" means

**Packaging** turns a design (HDL directory, a Vivado project, or a block design) into a
catalog entry: an *IP definition* directory containing the sources, the IP-XACT
metadata (`component.xml`), simulation/implementation models, and optionally the
`.xci` customisation files of the IP it uses internally, plus an example design
`[UG1118 §Supported IP Packager Inputs, §Outputs from IP Packager, §Packaging Your
Current Project]`.

Relevant rules for an agent that writes VHDL *destined to become IP*
`[UG1118 §Top-Level HDL Requirements]`:

* the packager supports Verilog and VHDL as a top-level; a **VHDL-2008 or SystemVerilog
  top must be wrapped in a Verilog/VHDL-2002 wrapper** before packaging;
* top-level ports must be `std_logic` / `std_logic_vector` for reliable VHDL
  simulation, because OOC synthesis converts netlist ports to those types anyway;
* clock interfaces are inferred from port names matching `[*_]clk`, `[*_]clkin`,
  `[*_]clock[_*]`, `[*_]aclk`, `[*_]aclkin` — otherwise create the interface manually
  and set the properties `[UG1118 §Inferring Clock Interfaces]`;
* avoid HDL keywords as identifiers;
* an IP containing other IP keeps only the `.xci` files, so the parent IP can become
  "locked" when a new Vivado release ships a newer version of the child IP — AMD
  recommends repackaging with an upgraded child `[UG1118 §Packaging Your Current
  Project]`;
* packaged IP is versioned and reusable; the IP packager wizard creates a temporary
  editing project for revisions `[UG1118 §Packaging Your Current Project]`.

Package a **block design** rather than loose HDL only when the deliverable really is a
subsystem with interfaces `[UG994 §Packaging a Block Design, §Introduction to Block
Design Containers]`.

### 6.3 Where IP Integrator (block design) belongs in a Zynq project

IP Integrator is the canvas/Tcl layer that instantiates IP from the catalog and connects
them by **interfaces** (groupings of signals such as AXI4-Lite, with design-rule checks
that verify the connection) `[UG994 §Getting Started with Vivado IP Integrator]`. It can
be driven entirely from Tcl, "programmatically through a Tcl programming interface"
`[UG994 §Getting Started with Vivado IP Integrator]`.

Typical Zynq-7020 (`xc7z020clg400`) usage — the PS side (dual-core Cortex-A9, DDR
controller, MIO, PLL/clock system, AXI master/slave ports) is documented in the Zynq-7000
TRM `[UG585]`:

```
processing_system7 (PS7: DDR, MIO, FCLK_CLK0, AXI GP0/HP0)
  -> axi_interconnect / smartconnect
  -> your VHDL block, wrapped as an AXI peripheral (or driven through AXI-Stream/FIFO)
  -> ILA on the AXI bus for bring-up
export -> XSA -> Vitis (bare-metal or Linux application)
```

The block design's address map is defined in the Address Editor; BDs can be nested as
Block Design Containers, each independently developed and reusable
`[UG994 §Introduction to Block Design Containers]`. Packages/export are handled through
`generate_target`, `make_wrapper`, `validate_bd_design` and `write_hw_platform`/XSA
export (see UG835 for exact syntax `[UG835 §generate_target]`).

### 6.4 When to **avoid** IP Integrator (LLM-specific)

Prefer plain VHDL + a small XDC when the design is PL-only, when no AXI/PS transaction
is needed, or when the deliverable must be diff-able text `[derived]`:

| Situation | Prefer | Why |
|---|---|---|
| PL-only datapath (FSM, datapath, filter, accelerator) with no PS | **Pure VHDL** (+ optional IP like ILA/FIFO) | No `.bd` file, no IP catalog dependency, deterministic project creation from a file list, easy to regenerate and review |
| Clock/reset generation | **Clocking Wizard IP or MMCM primitive** | Correct clocking is not worth hand-writing; the IP is versioned and gives you the lock/`locked` signal |
| CDC / FIFO | **XPM macros** (`XPM_CDC_*`, `XPM_FIFO_*`) or FIFO Generator | AMD's own recommendation: hand-written CDC "must be recognized" and needs `ASYNC_REG`; XPM guarantees recognition, MTBF reporting and avoids `report_cdc` errors `[UG949 §Clock Domain Crossing]` |
| Any PS-PL interaction (AXI, DDR, interrupts) | **IP Integrator** (generate the BD once, commit the Tcl + XSA) | Hand-writing AXI interconnect, address decode and clock domain logic is error-prone; IPI provides the DRCs and the address map `[UG994 §Getting Started with Vivado IP Integrator]` |
| Reusable deliverable to others | **Packaged IP** | Versioned interface with metadata `[UG1118]` |

Concrete rules that keep an LLM productive with IPI: generate the block design with
Tcl (never edit `.bd` by hand), commit the Tcl script and the exported hardware
handoff, keep the custom logic in VHDL outside the BD, and wrap it for the BD in a
separate `*_wrapper.vhd` so the block design only ever sees a stable interface.

### 6.5 Debug and validation hooks in the RTL

* `mark_debug` on a signal/port + insertion of an ILA core post-synthesis, or
  instantiation of the ILA in RTL: the ILA performs in-system debugging of
  post-implemented designs, triggers on hardware events and captures at system speed
  `[UG908 §ILA]`;
* VHDL syntax for the attribute:

```vhdl
attribute mark_debug : string;
attribute mark_debug of s_data_valid : signal is "true";
```
`[UG908 §Vivado Synthesis mark_debug Syntax Examples]`

* the same attribute can be applied from XDC (`set_property MARK_DEBUG TRUE [get_nets …]`)
  and the debug constraints (`create_debug_core`, `connect_debug_port`) are valid XDC
  commands `[UG903 §Valid Commands in an XDC File]`.

---

## 7. Devices, boards and their constraint families

### 7.1 Device families and Vivado part strings

Vivado part naming: `<family-prefix><device><package><speed-grade>[-temperature]`, e.g.
`xc7z020clg400-1`. Package code + pin count come from the packaging guide
(e.g. `CLG400` = wire-bond/chip-scale BGA family with 400 balls, 17×17 mm)
`[UG475 §Package Specifications Designations]`, `[DS190]`. Speed grade `-1` is the slowest
commercial grade of the family; the `L` suffix marks a low-power part (e.g.
`xc7a35ticsg324-1L`); `C`/`I` in vendor part strings means commercial/industrial
temperature.

| Family | Example Vivado part | Typical use | Clocking | Constraint notes |
|---|---|---|---|---|
| Artix-7 | `xc7a35tcpg236-1`, `xc7a100tcsg324-1`, `xc7a35ticsg324-1L` | teaching boards, low-cost logic | CMTs (each = 1 MMCM + 1 PLL); global and regional clock buffers | See the clocking row below; 3.3 V banks → `IOSTANDARD LVCMOS33` |
| Kintex-7 | `xc7k70tfbg484-1`, `xc7k325tffg900-2` | DSP-heavy, transceivers | 4 GTX (XC7K70T/FBG484) up to 32 GTX (XC7K480T/FFG1156) `[DS180]` | GTP/GTX transceivers need generated clocks on `RXOUTCLK`/`TXOUTCLK` `[UG903 §Primary Clocks Examples]` |
| Spartan-7 | `xc7s25csga324-1` | cheapest logic | CMTs (MMCM + PLL) | same BUFG rules; fewer global buffers |
| Zynq-7000 | `xc7z010clg400-1`, `xc7z020clg400-1`, `xc7z020clg484-1` | PS (Cortex-A9) + Artix-7-class PL `[DS190]` | PS PLLs + PL CMTs | PS clocks constrained by the PS7 IP; PL-only logic uses `create_clock` on its own port. No external I/O of the PL → Case B of §4.4 |
| Zynq UltraScale+ | `xczu3eg-sbva484-1-e`, `xczu9eg-ffvb1156-2-e` | PS (Cortex-A53) + UltraScale+ PL | PS PLLs, PL CMTs, BUFGCE_DIV | `BUFGCE_DIV` parallel buffers reduce clock uncertainty vs multiple MMCM outputs `[UG1292 §Improving Clock Uncertainty Techniques]` |
| Versal | `xcvc1902-vsva2197-2MP-e-S` | adaptive SoC | — | Use the Versal-specific flow (UG936); the concepts above still apply to the PL |

Constraints families to remember:

* **Clocks**: `create_clock` on the board port (always), `create_generated_clock` only
  for user-divided clocks, `set_clock_groups -asynchronous` for independent domains,
  `set_clock_uncertainty` for over-constraining, `set_propagated_clock` when you need
  post-route clock insertion delay `[UG903 §Valid Commands in an XDC File]`.
* **I/O**: `PACKAGE_PIN` + `IOSTANDARD` per port (per bank voltage), `DRIVE`/`SLEW` for
  outputs, `DIFF_TERM`/`IN_TERM` for differential, `IOB TRUE` to use I/O registers
  `[UG903 §I/O Constraints]`, `[UG471]`.
* **Gigabit transceivers**: `create_clock` on the reference clock port plus clocks
  recovered from `GT_CHANNEL` outputs `[UG903 §Primary Clocks]`.
* **Memory interfaces (MIG/DDR3)**: the pin-out and timing come from the MIG IP
  constraints; add only the system-level clocks on top.
* **7-series clock entry**: bring the user clock in on a clock-capable I/O pin; each
  I/O bank has clock-capable inputs that reach global/regional/I/O clock lines and the
  CMTs `[UG472 §Clock Routing Resources Overview]`; Vivado inserts the BUFG by default
  and the buffer type can be forced with the `CLOCK_BUFFER_TYPE` attribute
  (`BUFG`, `BUFH`, `BUFIO`, `BUFMR`, `BUFR`, or `none`), applicable to a top-level clock
  port in RTL or XDC `[UG901 §CLOCK_BUFFER_TYPE]`. A 7-series device has up to 24 clock
  management tiles (CMTs), each containing one MMCM and one PLL, plus BUFG/BUFGCE/
  BUFGMUX global and BUFH/BUFR/BUFIO regional buffers `[DS180]`, `[UG949 §7 Series
  Device Clocking]`.
* Example part strings for the newer families (`xczu3eg-sbva484-1-e`,
  `xcvc1902-…`) are **illustrative**: take the exact device/package/speed grade from the
  corresponding datasheet and `get_parts` in the installed tool, not from memory.

Device/package combinations and maximum I/Os for 7-series are tabulated in DS180
(Artix-7, Kintex-7, Virtex-7, Spartan-7) `[DS180]`; the Zynq-7000 device/package matrix
(including `CLG400` for `XC7Z020`) is in DS190 `[DS190]`.

### 7.2 Teaching boards — exact parts and XDC implications

| Board | FPGA on board (vendor string) | Vivado part to use | Notes for agents |
|---|---|---|---|
| **Basys 3** | `XC7A35T-1CPG236C` `[Digilent Basys 3 RM]` | `xc7a35tcpg236-1` | single-ended board clock on a CCIO pin; 3.3 V banks; master XDC from the vendor board file |
| **Nexys A7-100T** | `XC7A100T-1CSG324C` `[Digilent Nexys A7 RM]` | `xc7a100tcsg324-1` | same package as Arty A7-100T → reusable constraint skeleton, different pins |
| **Nexys A7-50T** | `XC7A50T-1CSG324I` `[Digilent Nexys A7 RM]` | `xc7a50tcsg324-1` | industrial grade variant |
| **Arty A7-100T** | `XC7A100TCSG324-1` `[Digilent Arty A7 RM]` | `xc7a100tcsg324-1` | MicroBlaze/soft-core oriented; 3.3 V Pmod headers |
| **Arty A7-35T** | `XC7A35TICSG324-1L` `[Digilent Arty A7 RM]` | `xc7a35ticsg324-1L` | **low-power `L` grade**: `-1L` parts have different timing; do not reuse a `-1` Fmax budget blindly |
| **Zybo Z7-20** | `XC7Z020-1CLG400C` `[Digilent Zybo Z7 RM]` | `xc7z020clg400-1` | Zynq: PS7 + PL; the PL clock usually comes from `FCLK_CLK0`, so PL-only sub-designs get their clock from the PS constraints |
| **Zybo Z7-10** | `XC7Z010-1CLG400C` `[Digilent Zybo Z7 RM]` | `xc7z010clg400-1` | smaller PL — check LUT/BRAM budget before generating |
| **PYNQ-Z2** | `XC7Z020-1CLG400C` `[TUL PYNQ-Z2]` | `xc7z020clg400-1` | same device as Zybo Z7-20 → same part string, different board pins; PYNQ/Python overlay flow |

Practical rules for board work `[derived]`:

* Take `PACKAGE_PIN` + `IOSTANDARD` + the board clock period from the vendor's **master
  XDC / board file** — never from memory. With board files installed, select the board
  (`set_property board_part <vendor>:<board>:part0:<rev> [current_project]`) and let
  Vivado bring in the master constraints instead of retyping pin lists.
* The board clock period is the single value that most affects results: `create_clock
  -period <T> [get_ports <clk>]` where `T` is the oscillator period from the board
  manual (100 MHz boards → 10.000 ns).
* A board file adds *peripheral* constraints (DDR, Ethernet, USB); a PL-only tutorial
  design needs only the clock, the buttons/switches and the LEDs — copy those few lines
  into `io.xdc` rather than importing the whole master XDC into a hand-made project.
* Keep one XDC per board in `src/constraints/<board>/` and select it per build; mixing
  two boards' pin constraints in one file guarantees conflicting `PACKAGE_PIN` values.

---

## 8. Sources

### 8.1 Documents (label → URL, version used)

| Label | Document | Version read | URL |
|---|---|---|---|
| `UG901` | Vivado Design Suite User Guide: Synthesis | 2026.1 (ed. 2026-07-08) | https://docs.amd.com/r/en-US/ug901-vivado-synthesis |
| `UG901 v2018.1` | same, older revision (used only where the current topic is empty: wait-statement rules, `real`, latch wording) | v2018.1 | https://docs.amd.com/r/en-US/ug901-vivado-synthesis (PDF mirror: https://docs.amd.com/api/khub/documents/M8zUaK8zmLMcJHmDf5emPw/content) |
| `UG903` | Vivado Design Suite User Guide: Using Constraints | 2026.1 (ed. 2026-07-01) | https://docs.amd.com/r/en-US/ug903-vivado-using-constraints |
| `UG906` | Vivado Design Suite User Guide: Design Analysis and Closure Techniques | 2026.1 | https://docs.amd.com/r/en-US/ug906-vivado-design-analysis |
| `UG908` | Vivado Design Suite User Guide: Programming and Debugging | 2026.1 | https://docs.amd.com/r/en-US/ug908-vivado-programming-debugging |
| `UG949` | UltraFast Design Methodology Guide for FPGAs and SoCs | 2026.1 | https://docs.amd.com/r/en-US/ug949-vivado-design-methodology |
| `UG973` | Vivado Release Notes, Installation and Licensing | 2026.1 | https://docs.amd.com/r/en-US/ug973-vivado-release-notes-install-license |
| `UG994` | Vivado Design Suite User Guide: Designing IP Subsystems Using IP Integrator | 2026.1 | https://docs.amd.com/r/en-US/ug994-vivado-ip-subsystems |
| `UG1118` | Vivado Design Suite User Guide: Creating and Packaging Custom IP | 2026.1 | https://docs.amd.com/r/en-US/ug1118-vivado-creating-packaging-custom-ip |
| `UG835` | Vivado Design Suite Tcl Command Reference Guide | 2026.1 | https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands |
| `UG1292` | UltraFast Design Methodology Timing Closure Quick Reference Guide | v2025.1 (2025-05-29) | https://docs.amd.com/api/khub/documents/tRbmKcEzeDj9iHna~g2y6g/content (PDF only) |
| `UG472` | 7 Series FPGAs Clocking Resources User Guide | v1.14 (2018-07-30) | https://docs.amd.com/v/u/en-US/ug472_7Series_Clocking |
| `UG475` | 7 Series FPGAs Packaging and Pinout Product Specification | v1.20 (2024-03-13) | https://docs.amd.com/v/u/en-US/ug475_7Series_Pkg_Pinout |
| `UG471` | 7 Series FPGAs SelectIO Resources | current (referenced, not re-read in full) | https://docs.amd.com/v/u/en-US/ug471_7Series_SelectIO |
| `UG585` | Zynq-7000 SoC Technical Reference Manual | v1.15 | https://docs.amd.com/r/en-US/ug585-zynq-7000-SoC-TRM |
| `DS180` | 7 Series FPGAs Data Sheet: Overview | current | https://docs.amd.com/v/u/en-US/ds180_7Series_Overview |
| `DS190` | Zynq-7000 SoC Family Product Selection Guide | 2019 revision (package/device matrix) | https://docs.amd.com/v/u/en-US/ds190-zynq-7000-product-selection-guide |
| `UG953` / `UG974` | 7 Series & Zynq-7000 Libraries Guide / UltraScale Architecture Libraries Guide (primitives, XPM) | last published 2020.1 (discontinued) | https://docs.amd.com/ (search UG953, UG974) |
| `IEEE 1076` | IEEE Standard for VHDL Language | IEEE 1076-2008 (2002 also relevant) | https://standards.ieee.org/ieee/1076/4405/ *(page not reachable from the machine used — cited as the language standard, content not re-verified here)* |

### 8.2 Topic-level URLs actually used (for claim-by-claim checking)

UG901: `/VHDL-Constructs-Support-Status`, `/VHDL-Sequential-Logic`,
`/VHDL-Combinatorial-Circuits`, `/Flip-Flops-Registers-and-Latches`,
`/Flip-Flops-and-Registers-Initialization`, `/VHDL-Initial-Values-and-Operational-Set/Reset`,
`/Latches`, `/Latches-Reporting-Example`, `/Supported-and-Unsupported-VHDL-Data-Types`,
`/VHDL-Objects`, `/VHDL-Real-Number-Constants`, `/VHDL-Predefined-Packages`,
`/Defining-Your-Own-VHDL-Packages`, `/VHDL-Functions-and-Procedures`,
`/VHDL-Component-Instantiation`, `/CLOCK_BUFFER_TYPE`, `/DIRECT_RESET`, `/EXTRACT_RESET`,
`/ASYNC_REG-VHDL-Examples`, `/RETIMING_FORWARD-VHDL-Example`, `/RETIMING_BACKWARD-VHDL-Example`,
`/VHDL-2008-Language-Support` — all under
`https://docs.amd.com/r/en-US/ug901-vivado-synthesis/<topic>`

UG903: `/About-XDC-Constraints`, `/Organizing-Your-Constraints`,
`/Creating-Synthesis-Constraints`, `/Creating-Implementation-Constraints`,
`/Entering-Constraints`, `/About-Clocks`, `/Primary-Clocks`, `/Primary-Clocks-Examples`,
`/Generated-Clocks`, `/User-Defined-Generated-Clocks`, `/Creating-Asynchronous-Clock-Groups`,
`/Input-Delays`, `/Output-Delays`, `/False-Paths`, `/Multicycle-Paths`,
`/Setting-Maximum-Delay-and-Minimum-Delay-Constraints`, `/I-O-Constraints`,
`/CLOCK-DEDICATED-ROUTE`, `/Valid-Commands-in-an-XDC-File` — all under
`https://docs.amd.com/r/en-US/ug903-vivado-using-constraints/<topic>`

UG949: `/Timing-Closure`, `/No-Clock-and-Unconstrained-Internal-Endpoints`,
`/Design-Constraints`, `/7-Series-Device-Clocking`, `/Clock-Domain-Crossing`,
`/Creating-Clock-Enables`, `/Reset-and-Clock-Enable-Precedence`, `/Gate-Clock-or-Data-Paths`
under `https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/<topic>`

UG906: `/Design-Timing-Summary-Section`, `/Check-Timing-Section`,
`/Unconstrained-Paths-Section`, `/Details-of-the-Timing-Summary-Report` under
`https://docs.amd.com/r/en-US/ug906-vivado-design-analysis/<topic>`

UG835: `/create_clock`, `/create_generated_clock`, `/set_input_delay`,
`/set_output_delay`, `/set_false_path`, `/set_clock_groups`, `/set_max_delay`,
`/set_property`, `/create_ip`, `/generate_target` under
`https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/<command>`

UG1118: `/Top-Level-HDL-Requirements`, `/Inferring-Clock-Interfaces`,
`/Packaging-Your-Current-Project`, `/Supported-IP-Packager-Inputs`,
`/Outputs-from-IP-Packager` under
`https://docs.amd.com/r/en-US/ug1118-vivado-creating-packaging-custom-ip/<topic>`

UG994: `/Getting-Started-with-Vivado-IP-Integrator`, `/Creating-a-Block-Design`,
`/Packaging-a-Block-Design`, `/Introduction-to-Block-Design-Containers` under
`https://docs.amd.com/r/en-US/ug994-vivado-ip-subsystems/<topic>`

UG908: `/ILA`, `/Vivado-Synthesis-mark_debug-Syntax-Examples`,
`/Debug-Hub` under `https://docs.amd.com/r/en-US/ug908-vivado-programming-debugging/<topic>`

UG973: `/Supported-Operating-Systems` under
`https://docs.amd.com/r/en-US/ug973-vivado-release-notes-install-license/Supported-Operating-Systems`

Boards (vendor documentation): Digilent Basys 3 reference manual
`https://digilent.com/reference/programmable-logic/basys-3/reference-manual`;
Digilent Nexys A7 `…/nexys-a7/reference-manual`; Digilent Arty A7
`…/arty-a7/reference-manual`; Digilent Zybo Z7 `…/zybo-z7/reference-manual`;
TUL PYNQ-Z2 `https://www.tulembedded.com/FPGA/ProductsPYNQ-Z2.html`.

### 8.3 Known gaps and uncertainties in this note

* `UG472`/`UG475`/`DS190` were read as PDFs (**v1.14 / v1.20 / 2019 revision**); the
  online 2026.1 reader no longer serves these documents, so their age is stated wherever
  they are cited.
* `UG1292` is only published as a PDF; the URL given is the download endpoint verified
  to return `UG1292 (v2025.1), 2025-05-29`.
* The IEEE 1076 page could not be fetched from the authoring machine (HTTP 403); the
  language-level rules marked `[IEEE 1076]` rest on standard VHDL semantics that are
  also reflected in UG901's construct table.
* No Vivado installation was used: the skeletons in §2 are written to the documented
  synthesis rules but have **not** been compiled here. Any agent using them should run
  `xvlog`/`xvhdl`+`synth_design` (or GHDL for a syntax gate) before claiming they work.
* Board clock frequencies/periods are intentionally not quoted per board: the exact
  oscillator period and the pin list must be taken from the vendor's master XDC
  (see §7.2), which was not reproduced here.

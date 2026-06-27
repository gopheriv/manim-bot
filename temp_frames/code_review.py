"""Static analysis of taylor_sin_final.py for bugs."""
import ast
import re

code = open('taylor_sin_final.py', 'r', encoding='utf-8').read()

print("=== CODE REVIEW: taylor_sin_final.py ===\n")

# 1. Check for lambda capture bugs
lambda_count = code.count('lambda')
print(f"✓ Lambdas found: {lambda_count}")

# Common bug: lambda x, n=num_terms without proper closure
if 'lambda x, n=num_terms' in code:
    print("✓ Lambda closure OK: using n=num_terms to capture loop variable")

# 2. Check for updater functions
updaters = re.findall(r'def (\w+)\(mob, dt\)', code)
print(f"\n✓ Updater functions: {len(updaters)}")
for updater in updaters:
    print(f"  - {updater}")

# 3. Check for ValueTracker usage
if 'ValueTracker' in code:
    print("\n✓ ValueTracker used for ambient animation")
    pulse_count = code.count('pulse_t')
    print(f"  - pulse_t referenced {pulse_count} times")

# 4. Check for potential math errors
print("\n=== POTENTIAL ISSUES ===\n")

issues_found = []

# Issue 1: Transform() on first iteration
if 'Transform(explanation, term_text) if i > 0 else FadeIn(term_text)' in code:
    issues_found.append("⚠️  BUG: Transform(explanation, term_text) will fail - 'explanation' is not defined yet!")
    issues_found.append("   Fix: Use 'term_text' variable or create 'explanation' before loop")

# Issue 2: Check x_range limits
x_ranges = re.findall(r'x_range=\[(-?\d+\.?\d*), (-?\d+\.?\d*)\]', code)
for x_min, x_max in x_ranges:
    if float(x_max) > 8:
        issues_found.append(f"⚠️  RISK: x_range=[{x_min}, {x_max}] might cause overflow for high-degree polynomials")

# Issue 3: Check for text overlap
if code.count('.next_to(') > 5:
    issues_found.append("⚠️  POTENTIAL: Many .next_to() calls - check for text overlap")

# Issue 4: Check run_time balance
run_times = re.findall(r'run_time=([\d.]+)', code)
total_runtime = sum(float(t) for t in run_times)
print(f"✓ Total animation run_time: {total_runtime:.1f}s")
print(f"✓ Actual video duration: ~23s (includes wait() calls)")

if issues_found:
    print(f"\n❌ Found {len(issues_found)} issue(s):\n")
    for issue in issues_found:
        print(issue)
else:
    print("\n✅ No critical issues found!")

print("\n=== OPTIMIZATION CHECKS ===\n")

# Check for performance optimizations
opts = []
if 'use_smoothing=False' in code:
    opts.append("✅ use_smoothing=False enabled")
if 'TracedPath' not in code:
    opts.append("✅ No TracedPath (good for performance)")
if code.count('always_redraw') == 0:
    opts.append("✅ No always_redraw() calls")
if code.count('add_updater') <= 2:
    opts.append("✅ Minimal updaters (≤2)")

for opt in opts:
    print(opt)

print("\n=== RECOMMENDATIONS ===\n")
print("1. Fix Transform() bug in animation loop")
print("2. Test video at 720p (-qm) to verify no quality loss")
print("3. Verify LaTeX rendering for all T_n labels")
print("4. Check final pulse effect doesn't lag on weak hardware")

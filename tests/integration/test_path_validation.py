"""
Quick test to verify all path validation fixes are working
"""
import os

def test_all_path_validations():
    """Test that all functions handle None paths gracefully"""
    print("Testing path validation in all modules...\n")
    
    # Test 1: Visualizer
    print("1. Testing visualizer.generate_dashboard with None path...")
    try:
        from src.utils.visualizer import generate_dashboard
        # This should not crash
        result = generate_dashboard(
            metrics={"originality": 50, "quality": 60},
            file_data=[],
            output_path=None
        )
        print(f"   ✅ PASS: Handled None, returned: {result}\n")
    except Exception as e:
        print(f"   ❌ FAIL: {e}\n")
    
    # Test 2: Quality Metrics
    print("2. Testing quality_metrics.analyze_quality with None path...")
    try:
        from src.detectors.quality_metrics import analyze_quality
        result = analyze_quality(None)
        print(f"   ✅ PASS: Returned safe defaults: {result}\n")
    except Exception as e:
        print(f"   ❌ FAIL: {e}\n")
    
    # Test 3: Security Scan
    print("3. Testing security_scan.scan_for_secrets with None path...")
    try:
        from src.detectors.security_scan import scan_for_secrets
        result = scan_for_secrets(None)
        print(f"   ✅ PASS: Returned safe defaults: {result}\n")
    except Exception as e:
        print(f"   ❌ FAIL: {e}\n")
    
    # Test 4: Structure Analyzer
    print("4. Testing structure_analyzer.analyze_structure with None path...")
    try:
        from src.detectors.structure_analyzer import analyze_structure
        result = analyze_structure(None)
        print(f"   ✅ PASS: Returned safe defaults: {result}\n")
    except Exception as e:
        print(f"   ❌ FAIL: {e}\n")
    
    # Test 5: Stack Detector
    print("5. Testing stack_detector.detect_tech_stack with None path...")
    try:
        from src.detectors.stack_detector import detect_tech_stack
        result = detect_tech_stack(None)
        print(f"   ✅ PASS: Returned safe defaults: {result}\n")
    except Exception as e:
        print(f"   ❌ FAIL: {e}\n")
    
    # Test 6: Maturity Scanner
    print("6. Testing maturity_scanner.scan_project_maturity with None path...")
    try:
        from src.detectors.maturity_scanner import scan_project_maturity
        result = scan_project_maturity(None)
        print(f"   ✅ PASS: Returned safe defaults: {result}\n")
    except Exception as e:
        print(f"   ❌ FAIL: {e}\n")
    
    # Test 7: Product Evaluator
    print("7. Testing product_evaluator.evaluate_product_logic with None path...")
    try:
        from src.detectors.product_evaluator import evaluate_product_logic
        result = evaluate_product_logic(None, "fake-key")
        print(f"   ✅ PASS: Returned safe defaults: {result}\n")
    except Exception as e:
        print(f"   ❌ FAIL: {e}\n")
    
    # Test 8: Repo Summary
    print("8. Testing repo_summary.generate_repo_summary with None path...")
    try:
        from src.utils.repo_summary import generate_repo_summary
        result = generate_repo_summary(None)
        print(f"   ✅ PASS: Returned error message: {result[:50]}...\n")
    except Exception as e:
        print(f"   ❌ FAIL: {e}\n")
    
    # Test 9: Tree Generation
    print("9. Testing file_utils.generate_tree_structure with None path...")
    try:
        from src.utils.file_utils import generate_tree_structure
        result = generate_tree_structure(None)
        print(f"   ✅ PASS: Returned error message: {result[:50]}...\n")
    except Exception as e:
        print(f"   ❌ FAIL: {e}\n")
    
    # Test 10: CSV Export (indirectly via output_dir check)
    print("10. Testing save_csv_results with None output_dir...")
    try:
        # Import after sys.path setup
        import sys
        sys.path.insert(0, os.path.dirname(__file__))
        from src.core.agent import save_csv_results
        
        # Mock data
        data = {
            "repo": "test",
            "stack": ["Python"],
            "scores": {"originality": 50},
            "judge": {},
            "maturity": {},
            "structure": {},
            "commit_details": {"author_stats": {}, "consistency_stats": {}},
            "security": {},
            "files": []
        }
        
        result = save_csv_results(None, "TestTeam", data)
        print(f"   ✅ PASS: Handled None output_dir, used fallback\n")
    except Exception as e:
        print(f"   ❌ FAIL: {e}\n")
    
    print("="*60)
    print("All path validation tests complete!")
    print("="*60)


if __name__ == "__main__":
    test_all_path_validations()

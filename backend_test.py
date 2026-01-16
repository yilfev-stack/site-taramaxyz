#!/usr/bin/env python3
"""
DEMART.COM.TR Web Sitesi Denetim Aracı - Backend API Test
Tests all API endpoints for the web audit tool
"""

import requests
import sys
import time
import json
from datetime import datetime

class DemartAPITester:
    def __init__(self, base_url="https://link-checker-17.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'DemartAPITester/1.0'
        })

    def log_test(self, name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name} - PASSED")
        else:
            print(f"❌ {name} - FAILED: {details}")
        return success

    def test_root_endpoint(self):
        """Test root API endpoint"""
        try:
            response = self.session.get(f"{self.api_url}/")
            success = response.status_code == 200
            if success:
                data = response.json()
                success = "Demart.com.tr" in data.get("message", "")
            return self.log_test("Root API Endpoint", success, 
                               f"Status: {response.status_code}")
        except Exception as e:
            return self.log_test("Root API Endpoint", False, str(e))

    def test_crawl_status(self):
        """Test crawl status endpoint"""
        try:
            response = self.session.get(f"{self.api_url}/crawl/status")
            success = response.status_code == 200
            if success:
                data = response.json()
                required_fields = ['status', 'crawled', 'discovered', 'issues', 'message']
                success = all(field in data for field in required_fields)
            return self.log_test("Crawl Status", success, 
                               f"Status: {response.status_code}")
        except Exception as e:
            return self.log_test("Crawl Status", False, str(e))

    def test_start_crawl(self):
        """Test starting a crawl"""
        try:
            payload = {
                "target_url": "https://www.demart.com.tr",
                "max_concurrent": 3
            }
            response = self.session.post(f"{self.api_url}/crawl/start", json=payload)
            success = response.status_code == 200
            if success:
                data = response.json()
                success = data.get("success", False)
            return self.log_test("Start Crawl", success, 
                               f"Status: {response.status_code}")
        except Exception as e:
            return self.log_test("Start Crawl", False, str(e))

    def test_report_summary(self):
        """Test report summary endpoint"""
        try:
            response = self.session.get(f"{self.api_url}/report/summary")
            success = response.status_code == 200
            if success:
                data = response.json()
                # Check if it's an error response or actual data
                if "error" not in data:
                    expected_fields = ['domain', 'total_urls', 'tr_pages', 'en_pages']
                    success = any(field in data for field in expected_fields)
                else:
                    # Error is expected if no crawl has been run yet
                    success = True
            return self.log_test("Report Summary", success, 
                               f"Status: {response.status_code}")
        except Exception as e:
            return self.log_test("Report Summary", False, str(e))

    def test_report_issues(self):
        """Test report issues endpoint with filters"""
        try:
            # Test without filters
            response = self.session.get(f"{self.api_url}/report/issues")
            success = response.status_code == 200
            if success:
                data = response.json()
                required_fields = ['issues', 'total', 'page', 'limit']
                success = all(field in data for field in required_fields)
            
            if success:
                # Test with filters
                params = {
                    'severity': 'Critical',
                    'language': 'TR',
                    'page': 1,
                    'limit': 10
                }
                response = self.session.get(f"{self.api_url}/report/issues", params=params)
                success = response.status_code == 200
            
            return self.log_test("Report Issues", success, 
                               f"Status: {response.status_code}")
        except Exception as e:
            return self.log_test("Report Issues", False, str(e))

    def test_report_urls(self):
        """Test report URLs endpoint"""
        try:
            response = self.session.get(f"{self.api_url}/report/urls")
            success = response.status_code == 200
            if success:
                data = response.json()
                required_fields = ['urls', 'total', 'page', 'limit']
                success = all(field in data for field in required_fields)
            return self.log_test("Report URLs", success, 
                               f"Status: {response.status_code}")
        except Exception as e:
            return self.log_test("Report URLs", False, str(e))

    def test_export_endpoints(self):
        """Test CSV and JSON export endpoints"""
        try:
            # Test CSV export
            response = self.session.get(f"{self.api_url}/report/export/csv")
            csv_success = response.status_code in [200, 404]  # 404 if no data
            
            # Test JSON export
            response = self.session.get(f"{self.api_url}/report/export/json")
            json_success = response.status_code in [200, 404]  # 404 if no data
            
            success = csv_success and json_success
            return self.log_test("Export Endpoints", success, 
                               f"CSV: {csv_success}, JSON: {json_success}")
        except Exception as e:
            return self.log_test("Export Endpoints", False, str(e))

    def test_report_stats(self):
        """Test report statistics endpoint"""
        try:
            response = self.session.get(f"{self.api_url}/report/stats")
            success = response.status_code == 200
            if success:
                data = response.json()
                # Should have stats structure even if empty
                success = isinstance(data, dict)
            return self.log_test("Report Stats", success, 
                               f"Status: {response.status_code}")
        except Exception as e:
            return self.log_test("Report Stats", False, str(e))

    def test_top_issues(self):
        """Test top issues endpoint"""
        try:
            response = self.session.get(f"{self.api_url}/report/top-issues?limit=5")
            success = response.status_code == 200
            if success:
                data = response.json()
                success = 'issues' in data and isinstance(data['issues'], list)
            return self.log_test("Top Issues", success, 
                               f"Status: {response.status_code}")
        except Exception as e:
            return self.log_test("Top Issues", False, str(e))

    def test_crawl_history(self):
        """Test crawl history endpoint"""
        try:
            response = self.session.get(f"{self.api_url}/history?limit=5")
            success = response.status_code == 200
            if success:
                data = response.json()
                success = 'reports' in data and isinstance(data['reports'], list)
            return self.log_test("Crawl History", success, 
                               f"Status: {response.status_code}")
        except Exception as e:
            return self.log_test("Crawl History", False, str(e))

    def test_stop_crawl(self):
        """Test stop crawl endpoint"""
        try:
            response = self.session.post(f"{self.api_url}/crawl/stop")
            success = response.status_code == 200
            if success:
                data = response.json()
                success = 'success' in data and 'message' in data
            return self.log_test("Stop Crawl", success, 
                               f"Status: {response.status_code}")
        except Exception as e:
            return self.log_test("Stop Crawl", False, str(e))

    def wait_for_crawl_completion(self, timeout=60):
        """Wait for crawl to complete or timeout"""
        print(f"\n⏳ Waiting for crawl to complete (timeout: {timeout}s)...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                response = self.session.get(f"{self.api_url}/crawl/status")
                if response.status_code == 200:
                    data = response.json()
                    status = data.get('status', 'unknown')
                    crawled = data.get('crawled', 0)
                    discovered = data.get('discovered', 0)
                    issues = data.get('issues', 0)
                    
                    print(f"Status: {status}, Crawled: {crawled}, Discovered: {discovered}, Issues: {issues}")
                    
                    if status in ['completed', 'error', 'stopped']:
                        return status == 'completed'
                    
                time.sleep(3)
            except Exception as e:
                print(f"Error checking status: {e}")
                time.sleep(3)
        
        print("⚠️ Crawl timeout reached")
        return False

    def run_full_test_suite(self):
        """Run complete test suite"""
        print("🚀 Starting DEMART API Test Suite")
        print(f"🔗 Testing API: {self.api_url}")
        print("=" * 60)
        
        # Basic API tests
        self.test_root_endpoint()
        self.test_crawl_status()
        self.test_report_summary()
        self.test_report_issues()
        self.test_report_urls()
        self.test_export_endpoints()
        self.test_report_stats()
        self.test_top_issues()
        self.test_crawl_history()
        
        # Test crawl functionality
        print("\n🔄 Testing Crawl Functionality")
        crawl_started = self.test_start_crawl()
        
        if crawl_started:
            # Wait a bit for crawl to start
            time.sleep(5)
            
            # Check if crawl is running
            try:
                response = self.session.get(f"{self.api_url}/crawl/status")
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status') == 'running':
                        print("✅ Crawl is running, waiting for completion...")
                        completed = self.wait_for_crawl_completion(timeout=120)
                        if completed:
                            print("✅ Crawl completed successfully!")
                            # Test endpoints with data
                            print("\n📊 Testing endpoints with crawl data...")
                            self.test_report_summary()
                            self.test_report_issues()
                            self.test_report_urls()
                            self.test_export_endpoints()
                        else:
                            print("⚠️ Crawl did not complete in time")
                    else:
                        print(f"⚠️ Crawl status: {data.get('status')}")
        
        # Test stop functionality
        self.test_stop_crawl()
        
        # Print results
        print("\n" + "=" * 60)
        print(f"📊 Test Results: {self.tests_passed}/{self.tests_run} passed")
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        print(f"📈 Success Rate: {success_rate:.1f}%")
        
        if success_rate >= 80:
            print("🎉 Backend API tests mostly successful!")
            return True
        else:
            print("⚠️ Backend API has significant issues")
            return False

def main():
    """Main test function"""
    tester = DemartAPITester()
    success = tester.run_full_test_suite()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
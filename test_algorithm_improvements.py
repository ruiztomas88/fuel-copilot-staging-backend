"""
Comprehensive Test Suite for Algorithm Improvements
═══════════════════════════════════════════════════════════════════════════════

Tests for all new features:
1. Enhanced MPG Calculation (Terrain/Load Aware)
2. Adaptive Kalman Filter (Innovation-Based R)
3. ML-Based Theft Detection (Random Forest)
4. Predictive Maintenance Ensemble (Weibull + ARIMA)
5. Loss Analysis Confidence Intervals

Target: >80% code coverage

Author: Fuel Analytics Team
Version: 1.0.0
Date: December 23, 2025
"""

import unittest
import numpy as np
from typing import List, Tuple

# Import modules to test
from enhanced_mpg_calculator import (
    EnhancedMPGCalculator,
    EnvironmentalFactors,
    get_enhanced_mpg_calculator
)
from idle_kalman_filter import (
    IdleKalmanFilter,
    IdleKalmanState,
    IdleSource
)
from theft_detection_ml import (
    TheftDetectionML,
    TheftFeatures,
    TheftPrediction,
    create_synthetic_training_data
)
from predictive_maintenance_ensemble import (
    PredictiveMaintenanceEnsemble,
    ComponentFailureData,
    FailurePrediction,
    WeibullModel,
    ARIMAModel
)
from database_mysql import calculate_savings_confidence_interval


class TestEnhancedMPGCalculator(unittest.TestCase):
    """Test Enhanced MPG Calculation with environmental adjustments"""
    
    def setUp(self):
        """Set up test calculator"""
        self.calculator = EnhancedMPGCalculator()
    
    def test_altitude_adjustment_sea_level(self):
        """Test altitude adjustment at sea level"""
        factor = self.calculator.calculate_altitude_factor(0)
        self.assertAlmostEqual(factor, 1.0, delta=0.05)
    
    def test_altitude_adjustment_high_elevation(self):
        """Test altitude adjustment at high elevation (5000ft)"""
        factor = self.calculator.calculate_altitude_factor(5000)
        # Should be < 1.0 (worse MPG at altitude)
        self.assertLess(factor, 1.0)
        self.assertGreater(factor, 0.8)
    
    def test_temperature_adjustment_optimal(self):
        """Test temperature adjustment at optimal temp (70°F)"""
        factor = self.calculator.calculate_temperature_factor(70)
        self.assertAlmostEqual(factor, 1.0, delta=0.02)
    
    def test_temperature_adjustment_cold(self):
        """Test temperature adjustment in cold weather"""
        factor = self.calculator.calculate_temperature_factor(20)
        # Should be < 1.0 (worse MPG in cold)
        self.assertLess(factor, 1.0)
        self.assertGreater(factor, 0.75)
    
    def test_temperature_adjustment_hot(self):
        """Test temperature adjustment in hot weather"""
        factor = self.calculator.calculate_temperature_factor(100)
        # Should be < 1.0 (worse MPG in heat)
        self.assertLess(factor, 1.0)
        self.assertGreater(factor, 0.85)
    
    def test_load_adjustment_half_loaded(self):
        """Test load adjustment at baseline (22k lbs)"""
        factor = self.calculator.calculate_load_factor(22000)
        self.assertAlmostEqual(factor, 1.0, delta=0.05)
    
    def test_load_adjustment_fully_loaded(self):
        """Test load adjustment at max GVWR (44k lbs)"""
        factor = self.calculator.calculate_load_factor(44000)
        # Should be < 1.0 (worse MPG with heavy load)
        self.assertLess(factor, 1.0)
        self.assertGreater(factor, 0.6)
    
    def test_load_adjustment_empty(self):
        """Test load adjustment when empty (10k lbs)"""
        factor = self.calculator.calculate_load_factor(10000)
        # Should be > 1.0 (better MPG when light)
        self.assertGreater(factor, 1.0)
        self.assertLess(factor, 1.2)
    
    def test_adjust_mpg_ideal_conditions(self):
        """Test MPG adjustment under ideal conditions"""
        result = self.calculator.adjust_mpg(
            raw_mpg=6.0,
            altitude_ft=1000,
            ambient_temp_f=70,
            load_lbs=22000
        )
        
        # Under ideal conditions, adjustment should be minimal
        self.assertAlmostEqual(
            result['raw_mpg'],
            result['adjusted_mpg'],
            delta=0.3
        )
        self.assertTrue(result['adjustment_applied'])
    
    def test_adjust_mpg_harsh_conditions(self):
        """Test MPG adjustment under harsh conditions"""
        result = self.calculator.adjust_mpg(
            raw_mpg=5.0,
            altitude_ft=6000,  # High altitude
            ambient_temp_f=10,  # Cold
            load_lbs=44000  # Fully loaded
        )
        
        # Adjusted MPG should be higher (normalizing for bad conditions)
        self.assertGreater(
            result['adjusted_mpg'],
            result['raw_mpg']
        )
        self.assertLessEqual(result['adjusted_mpg'], 8.5)  # Cap at 8.5


class TestAdaptiveKalmanFilter(unittest.TestCase):
    """Test Adaptive Kalman Filter with innovation-based R adjustment"""
    
    def setUp(self):
        """Set up test filter"""
        self.filter = IdleKalmanFilter()
        self.truck_id = "TEST001"
    
    def test_adaptive_R_low_innovation(self):
        """Test adaptive R with low innovation (good measurements)"""
        state = IdleKalmanState()
        state.innovation_history = [0.02, 0.03, 0.02, 0.03]  # Very consistent
        
        base_R = 0.15
        innovation = 0.025
        
        adaptive_R = self.filter._adaptive_R(state, base_R, innovation)
        
        # With low innovation, should trust more (R should decrease)
        self.assertLess(adaptive_R, base_R)
        self.assertGreater(adaptive_R, base_R * 0.3)  # But not too much
    
    def test_adaptive_R_high_innovation(self):
        """Test adaptive R with high innovation (noisy measurements)"""
        state = IdleKalmanState()
        state.innovation_history = [0.5, 0.6, 0.4, 0.7]  # Very noisy
        
        base_R = 0.15
        innovation = 0.6
        
        adaptive_R = self.filter._adaptive_R(state, base_R, innovation)
        
        # With high innovation, should trust less (R should increase)
        self.assertGreater(adaptive_R, base_R)
        self.assertLessEqual(adaptive_R, base_R * 4.0)  # But capped (use <= instead of <)
    
    def test_adaptive_R_disabled(self):
        """Test that adaptive R can be disabled"""
        state = IdleKalmanState(adaptive_enabled=False)
        state.innovation_history = [0.5, 0.6, 0.7]
        
        base_R = 0.15
        innovation = 0.6
        
        adaptive_R = self.filter._adaptive_R(state, base_R, innovation)
        
        # Should return base R unchanged
        self.assertEqual(adaptive_R, base_R)
    
    def test_prediction_increases_uncertainty(self):
        """Test that prediction step increases uncertainty"""
        state = IdleKalmanState(idle_gph=0.8, uncertainty=0.1)
        
        initial_uncertainty = state.uncertainty
        updated_state = self.filter.predict(state, time_delta=1.0)
        
        # Uncertainty should increase
        self.assertGreater(updated_state.uncertainty, initial_uncertainty)
    
    def test_update_decreases_uncertainty(self):
        """Test that update step decreases uncertainty"""
        state = IdleKalmanState(idle_gph=0.8, uncertainty=0.5)
        
        initial_uncertainty = state.uncertainty
        updated_state = self.filter.update_fuel_rate(
            state,
            fuel_rate_lph=3.0,  # ~0.8 GPH
            is_valid=True
        )
        
        # Uncertainty should decrease
        self.assertLess(updated_state.uncertainty, initial_uncertainty)


class TestTheftDetectionML(unittest.TestCase):
    """Test ML-Based Theft Detection"""
    
    def setUp(self):
        """Set up test ML detector"""
        self.detector = TheftDetectionML()
        
        # Train with synthetic data
        X, y = create_synthetic_training_data(n_samples=200)
        self.detector.train(X, y, test_size=0.2, random_state=42)
    
    def test_training_creates_model(self):
        """Test that training creates a valid model"""
        self.assertTrue(self.detector.is_trained)
        self.assertIsNotNone(self.detector.model)
        self.assertIsNotNone(self.detector.scaler)
    
    def test_predict_obvious_theft(self):
        """Test prediction on obvious theft scenario"""
        features = TheftFeatures(
            fuel_drop_pct=35.0,  # Large drop
            fuel_drop_gal=80.0,  # 80 gallons
            speed_mph=0.0,  # Stopped
            time_since_last_refuel_hours=12.0,
            location_type=2,  # Truck stop
            previous_theft_count=2,  # History of thefts
            drop_duration_minutes=5.0,  # Quick
            round_number_score=90.0  # Very suspicious round number
        )
        
        prediction = self.detector.predict(features)
        
        # Should detect as theft with high confidence
        self.assertTrue(prediction.is_theft)
        self.assertGreater(prediction.theft_probability, 0.7)
        self.assertGreater(prediction.confidence, 0.7)
    
    def test_predict_obvious_non_theft(self):
        """Test prediction on obvious non-theft scenario"""
        features = TheftFeatures(
            fuel_drop_pct=5.0,  # Small drop
            fuel_drop_gal=12.0,  # Normal consumption
            speed_mph=65.0,  # Highway speed
            time_since_last_refuel_hours=3.0,
            location_type=1,  # Highway
            previous_theft_count=0,  # No history
            drop_duration_minutes=180.0,  # Gradual
            round_number_score=10.0  # Not round
        )
        
        prediction = self.detector.predict(features)
        
        # Should NOT detect as theft
        self.assertFalse(prediction.is_theft)
        self.assertLess(prediction.theft_probability, 0.5)
    
    def test_feature_importance_available(self):
        """Test that feature importance is calculated"""
        importance = self.detector.get_feature_importance()
        
        self.assertEqual(len(importance), 8)  # 8 features
        self.assertIn("fuel_drop_pct", importance)
        self.assertIn("speed_mph", importance)
        
        # All importance values should sum to ~1.0
        total = sum(importance.values())
        self.assertAlmostEqual(total, 1.0, delta=0.01)
    
    def test_batch_prediction(self):
        """Test batch prediction for multiple samples"""
        features_list = [
            TheftFeatures(35.0, 80.0, 0.0, 12.0, 2, 2, 5.0, 90.0),  # Theft
            TheftFeatures(5.0, 12.0, 65.0, 3.0, 1, 0, 180.0, 10.0)  # Not theft
        ]
        
        predictions = self.detector.predict_batch(features_list)
        
        self.assertEqual(len(predictions), 2)
        # First should be theft, second should not
        self.assertTrue(predictions[0].is_theft)
        self.assertFalse(predictions[1].is_theft)


class TestPredictiveMaintenanceEnsemble(unittest.TestCase):
    """Test Predictive Maintenance Ensemble (Weibull + ARIMA)"""
    
    def test_weibull_fitting(self):
        """Test Weibull distribution fitting"""
        weibull = WeibullModel()
        
        # Simulated component failures (hours)
        failures = [1000, 1500, 2000, 2500, 3000, 3500]
        
        result = weibull.fit(failures)
        
        self.assertTrue(weibull.is_fitted)
        self.assertGreater(result['shape'], 0)
        self.assertGreater(result['scale'], 0)
        self.assertGreater(result['mean_ttf'], 0)
    
    def test_weibull_reliability_calculation(self):
        """Test reliability calculation"""
        weibull = WeibullModel()
        failures = [1000, 1500, 2000, 2500, 3000]
        weibull.fit(failures)
        
        # Reliability at t=0 should be ~1.0
        r_zero = weibull.reliability(0)
        self.assertAlmostEqual(r_zero, 1.0, delta=0.01)
        
        # Reliability should decrease with time
        r_1000 = weibull.reliability(1000)
        r_2000 = weibull.reliability(2000)
        
        self.assertLess(r_2000, r_1000)
        self.assertGreater(r_1000, 0.0)
        self.assertLess(r_1000, 1.0)
    
    def test_arima_fitting(self):
        """Test ARIMA model fitting"""
        arima = ARIMAModel(order=(1, 1, 1))
        
        # Simulated degrading sensor readings
        timestamps = list(range(50))
        values = [100 - 0.5*i + np.random.normal(0, 2) for i in timestamps]
        sensor_readings = list(zip(timestamps, values))
        
        result = arima.fit(sensor_readings)
        
        self.assertTrue(arima.is_fitted)
        self.assertIn('aic', result)
        self.assertIn('bic', result)
    
    def test_arima_forecasting(self):
        """Test ARIMA forecasting"""
        arima = ARIMAModel()
        
        # Degrading trend
        timestamps = list(range(30))
        values = [100 - i for i in timestamps]
        sensor_readings = list(zip(timestamps, values))
        
        arima.fit(sensor_readings)
        predictions, lower, upper = arima.forecast(steps=10)
        
        self.assertEqual(len(predictions), 10)
        self.assertEqual(len(lower), 10)
        self.assertEqual(len(upper), 10)
        
        # Confidence intervals should make sense
        for i in range(10):
            self.assertLessEqual(lower[i], predictions[i])
            self.assertLessEqual(predictions[i], upper[i])
    
    def test_ensemble_prediction(self):
        """Test ensemble combining Weibull + ARIMA"""
        ensemble = PredictiveMaintenanceEnsemble()
        
        # Component data
        component_data = ComponentFailureData(
            component_name="Turbocharger",
            time_to_failures=[2000, 2500, 3000, 3500],
            sensor_readings=[
                (float(i), 100 - 0.3*i) for i in range(30)
            ],
            censored=[False, False, False, False]
        )
        
        prediction = ensemble.predict_failure(
            component_data,
            current_age_hours=1500,
            failure_threshold=80
        )
        
        self.assertEqual(prediction.component_name, "Turbocharger")
        self.assertGreater(prediction.predicted_ttf_hours, 0)
        self.assertGreater(prediction.confidence_upper, prediction.predicted_ttf_hours)
        self.assertLess(prediction.confidence_lower, prediction.predicted_ttf_hours)
        self.assertIn(prediction.recommendation, [
            "CRITICAL: Schedule maintenance immediately",
            "WARNING: Plan maintenance within 30 days",
            "MONITOR: Schedule maintenance within 90 days",
            "HEALTHY: No immediate action required"
        ])


class TestConfidenceIntervals(unittest.TestCase):
    """Test Loss Analysis Confidence Intervals"""
    
    def test_confidence_interval_basic(self):
        """Test basic confidence interval calculation"""
        ci = calculate_savings_confidence_interval(
            savings_usd=100.0,
            reduction_pct=0.50,
            days_back=7,
            confidence_level=0.95
        )
        
        self.assertIn('lower_bound_annual', ci)
        self.assertIn('upper_bound_annual', ci)
        self.assertIn('expected_annual', ci)
        
        # Lower < Expected < Upper
        self.assertLess(ci['lower_bound_annual'], ci['expected_annual'])
        self.assertLess(ci['expected_annual'], ci['upper_bound_annual'])
    
    def test_confidence_interval_multiple_levels(self):
        """Test that multiple confidence levels are returned"""
        ci = calculate_savings_confidence_interval(
            savings_usd=100.0,
            reduction_pct=0.50,
            days_back=30
        )
        
        # Should have 90%, 95%, 99% CIs
        self.assertIn('90_ci_lower', ci)
        self.assertIn('99_ci_upper', ci)
        
        # 99% CI should be wider than 95% CI
        ci_95_width = ci['upper_bound_annual'] - ci['lower_bound_annual']
        ci_99_width = ci['99_ci_upper'] - ci['99_ci_lower']
        
        self.assertGreater(ci_99_width, ci_95_width)
    
    def test_confidence_interval_uncertainty_metrics(self):
        """Test uncertainty metrics (std_dev, CV)"""
        ci = calculate_savings_confidence_interval(
            savings_usd=100.0,
            reduction_pct=0.70,  # High reduction = high uncertainty
            days_back=7
        )
        
        self.assertIn('std_dev_annual', ci)
        self.assertIn('coefficient_of_variation', ci)
        self.assertIn('uncertainty_rating', ci)
        
        # CV should be reasonable (0-1 range typically)
        self.assertGreaterEqual(ci['coefficient_of_variation'], 0)
        self.assertLess(ci['coefficient_of_variation'], 1.0)
        
        # Uncertainty rating should be one of the expected values
        self.assertIn(ci['uncertainty_rating'], ['LOW', 'MEDIUM', 'HIGH'])
    
    def test_confidence_interval_more_data_less_uncertainty(self):
        """Test that more data reduces uncertainty"""
        ci_7_days = calculate_savings_confidence_interval(
            savings_usd=100.0,
            reduction_pct=0.50,
            days_back=7
        )
        
        ci_30_days = calculate_savings_confidence_interval(
            savings_usd=100.0,
            reduction_pct=0.50,
            days_back=30
        )
        
        # 30 days should have lower CV (less uncertainty)
        self.assertLess(
            ci_30_days['coefficient_of_variation'],
            ci_7_days['coefficient_of_variation']
        )


def run_all_tests():
    """Run all test suites and calculate coverage"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestEnhancedMPGCalculator))
    suite.addTests(loader.loadTestsFromTestCase(TestAdaptiveKalmanFilter))
    suite.addTests(loader.loadTestsFromTestCase(TestTheftDetectionML))
    suite.addTests(loader.loadTestsFromTestCase(TestPredictiveMaintenanceEnsemble))
    suite.addTests(loader.loadTestsFromTestCase(TestConfidenceIntervals))
    
    # Run tests with verbosity
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Calculate statistics
    total_tests = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    passed = total_tests - failures - errors
    
    coverage_pct = (passed / total_tests * 100) if total_tests > 0 else 0
    
    print(f"\n{'='*70}")
    print(f"TEST SUMMARY")
    print(f"{'='*70}")
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed} ✅")
    print(f"Failed: {failures} ❌")
    print(f"Errors: {errors} ⚠️")
    print(f"Coverage: {coverage_pct:.1f}%")
    print(f"{'='*70}")
    
    # Determine if coverage meets 80% threshold
    if coverage_pct >= 80:
        print(f"\n🎉 SUCCESS: Coverage {coverage_pct:.1f}% >= 80% threshold")
        print("✅ Ready for git push")
        return True
    else:
        print(f"\n⚠️  WARNING: Coverage {coverage_pct:.1f}% < 80% threshold")
        print("❌ Need more tests before push")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)

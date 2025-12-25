"""
Example 5: Frontend Dashboard Component - Truck MPG vs Baseline

TypeScript/React component to show truck MPG performance against baseline
"""

# This would be a TypeScript file in your frontend
# /Users/tomasruiz/Desktop/Fuel-Analytics-Frontend/src/components/TruckMPGComparison.tsx

typescript_code = """
import React, { useEffect, useState } from 'react';
import { TrendingUp, TrendingDown, AlertTriangle, CheckCircle } from 'lucide-react';

interface TruckSpecs {
  truck_id: string;
  year: number;
  make: string;
  model: string;
  baseline_mpg_loaded: number;
  baseline_mpg_empty: number;
  age_years: number;
}

interface TruckMPGData {
  truck_id: string;
  specs: TruckSpecs;
  current_mpg: number;
  expected_mpg: number;
  deviation_pct: number;
  status: 'GOOD' | 'NORMAL' | 'WARNING' | 'CRITICAL';
}

export default function TruckMPGComparison() {
  const [trucks, setTrucks] = useState<TruckMPGData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Fetch truck specs and current MPG
    Promise.all([
      fetch('/api/truck-specs/').then(r => r.json()),
      fetch('/api/trucks/current-mpg').then(r => r.json())
    ]).then(([specs, currentMPG]) => {
      const truckData = Object.entries(specs).map(([truck_id, spec]: any) => {
        const current = currentMPG[truck_id] || 0;
        const expected = spec.baseline_mpg_loaded;
        const deviation = ((current - expected) / expected) * 100;
        
        let status: TruckMPGData['status'];
        if (deviation >= 0) status = 'GOOD';
        else if (deviation >= -12.5) status = 'NORMAL';
        else if (deviation >= -25) status = 'WARNING';
        else status = 'CRITICAL';
        
        return {
          truck_id,
          specs: spec,
          current_mpg: current,
          expected_mpg: expected,
          deviation_pct: deviation,
          status
        };
      });
      
      setTrucks(truckData.sort((a, b) => a.deviation_pct - b.deviation_pct));
      setLoading(false);
    });
  }, []);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'GOOD': return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'NORMAL': return <TrendingUp className="w-5 h-5 text-blue-500" />;
      case 'WARNING': return <TrendingDown className="w-5 h-5 text-yellow-500" />;
      case 'CRITICAL': return <AlertTriangle className="w-5 h-5 text-red-500" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'GOOD': return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200';
      case 'NORMAL': return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200';
      case 'WARNING': return 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200';
      case 'CRITICAL': return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200';
      default: return '';
    }
  };

  if (loading) return <div>Loading truck comparison...</div>;

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-bold">MPG Performance vs Baseline</h2>
      
      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4">
        <div className="card bg-green-50 dark:bg-green-900/20 border-l-4 border-green-500">
          <div className="text-sm text-gray-600 dark:text-gray-400">Exceeding Baseline</div>
          <div className="text-3xl font-bold text-green-600">
            {trucks.filter(t => t.status === 'GOOD').length}
          </div>
        </div>
        
        <div className="card bg-blue-50 dark:bg-blue-900/20 border-l-4 border-blue-500">
          <div className="text-sm text-gray-600 dark:text-gray-400">Normal Range</div>
          <div className="text-3xl font-bold text-blue-600">
            {trucks.filter(t => t.status === 'NORMAL').length}
          </div>
        </div>
        
        <div className="card bg-yellow-50 dark:bg-yellow-900/20 border-l-4 border-yellow-500">
          <div className="text-sm text-gray-600 dark:text-gray-400">Below Expected</div>
          <div className="text-3xl font-bold text-yellow-600">
            {trucks.filter(t => t.status === 'WARNING').length}
          </div>
        </div>
        
        <div className="card bg-red-50 dark:bg-red-900/20 border-l-4 border-red-500">
          <div className="text-sm text-gray-600 dark:text-gray-400">Critical</div>
          <div className="text-3xl font-bold text-red-600">
            {trucks.filter(t => t.status === 'CRITICAL').length}
          </div>
        </div>
      </div>

      {/* Truck List */}
      <div className="card overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 dark:bg-gray-800">
            <tr>
              <th className="px-4 py-3 text-left">Truck</th>
              <th className="px-4 py-3 text-left">Make/Model</th>
              <th className="px-4 py-3 text-center">Year</th>
              <th className="px-4 py-3 text-center">Expected MPG</th>
              <th className="px-4 py-3 text-center">Current MPG</th>
              <th className="px-4 py-3 text-center">Deviation</th>
              <th className="px-4 py-3 text-center">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
            {trucks.map(truck => (
              <tr key={truck.truck_id} className="hover:bg-gray-50 dark:hover:bg-gray-800">
                <td className="px-4 py-3 font-mono font-bold">{truck.truck_id}</td>
                <td className="px-4 py-3">{truck.specs.make} {truck.specs.model}</td>
                <td className="px-4 py-3 text-center">{truck.specs.year}</td>
                <td className="px-4 py-3 text-center font-semibold text-gray-600">
                  {truck.expected_mpg.toFixed(1)}
                </td>
                <td className="px-4 py-3 text-center font-bold">
                  {truck.current_mpg.toFixed(1)}
                </td>
                <td className={`px-4 py-3 text-center font-semibold ${
                  truck.deviation_pct >= 0 ? 'text-green-600' : 'text-red-600'
                }`}>
                  {truck.deviation_pct > 0 ? '+' : ''}{truck.deviation_pct.toFixed(1)}%
                </td>
                <td className="px-4 py-3 text-center">
                  <div className="flex items-center justify-center gap-2">
                    {getStatusIcon(truck.status)}
                    <span className={`px-2 py-1 rounded text-xs font-semibold ${getStatusColor(truck.status)}`}>
                      {truck.status}
                    </span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
"""

print(typescript_code)

# Instructions:
print(
    """
═══════════════════════════════════════════════════════════════════════════════
TO ADD THIS TO YOUR FRONTEND:
═══════════════════════════════════════════════════════════════════════════════

1. Create the file:
   /Users/tomasruiz/Desktop/Fuel-Analytics-Frontend/src/components/TruckMPGComparison.tsx

2. Add a route in your router (src/App.tsx or routes):
   <Route path="/truck-specs" element={<TruckMPGComparison />} />

3. Add navigation link:
   <NavLink to="/truck-specs">
     <Truck className="w-4 h-4" />
     <span>Truck Specs</span>
   </NavLink>

4. Make sure backend API endpoints are exposed:
   - GET /api/truck-specs/ (all specs)
   - GET /api/trucks/current-mpg (current MPG for all trucks)

═══════════════════════════════════════════════════════════════════════════════
"""
)

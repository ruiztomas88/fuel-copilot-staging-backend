-- Create remote user for Mac access
CREATE USER IF NOT EXISTS 'fuel_admin'@'%' IDENTIFIED BY 'FuelCopilot2025!';
GRANT ALL PRIVILEGES ON fuel_copilot.* TO 'fuel_admin'@'%';
FLUSH PRIVILEGES;

-- Verify
SELECT User, Host FROM mysql.user WHERE User = 'fuel_admin';

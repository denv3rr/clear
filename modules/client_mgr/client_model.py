import uuid
from dataclasses import dataclass, field
from typing import List, Dict

@dataclass
class Account:
    """A single investment account held by a client."""
    account_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    account_name: str = "Brokerage Account"
    account_type: str = "Taxable"  # e.g., Taxable, IRA, 401k
    current_value: float = 0.0
    
    # Simple list of holdings: {ticker: quantity}
    holdings: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self):
        """Converts the Account object to a dictionary for JSON serialization."""
        return self.__dict__

@dataclass
class Client:
    """The central client profile."""
    client_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "New Client"
    risk_profile: str = "Moderate" # MANUALLY defined risk profile: Conservative, Moderate, Aggressive
    calculated_risk: str = "N/A"   # Field for model result
    accounts: List[Account] = field(default_factory=list)
    
    def to_dict(self):
        """Converts the Client object and its nested Accounts to a serializable dictionary."""
        return {
            "client_id": self.client_id,
            "name": self.name,
            "risk_profile": self.risk_profile,
            "calculated_risk": self.calculated_risk,
            "accounts": [acc.to_dict() for acc in self.accounts]
        }
    
    @staticmethod
    def from_dict(data: dict):
        """Re-creates the Client object from a dictionary loaded from JSON."""
        client = Client(
            client_id=data['client_id'],
            name=data['name'],
            risk_profile=data.get('risk_profile', 'Moderate'),
            calculated_risk=data.get('calculated_risk', 'N/A'),
            accounts=[]
        )
        
        # Reconstruct nested Account objects
        for acc_data in data.get('accounts', []):
            account = Account(
                account_id=acc_data.get('account_id', str(uuid.uuid4())),
                account_name=acc_data.get('account_name', 'Brokerage Account'),
                account_type=acc_data.get('account_type', 'Taxable'),
                current_value=acc_data.get('current_value', 0.0),
                holdings=acc_data.get('holdings', {})
            )
            client.accounts.append(account)
            
        return client
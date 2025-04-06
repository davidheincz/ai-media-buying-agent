"""
Knowledge Processing Module for DeepSeek Integration

This module provides functionality for processing and managing knowledge
extracted from media buying documents using DeepSeek AI.
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('knowledge_processor')

class KnowledgeProcessor:
    """Class for processing and managing knowledge extracted from documents."""
    
    def __init__(self, knowledge_base_path: Optional[str] = None):
        """Initialize the knowledge processor.
        
        Args:
            knowledge_base_path: Path to the knowledge base file. If None, will use default path.
        """
        self.knowledge_base_path = knowledge_base_path or os.path.join(
            os.getcwd(), 'data', 'knowledge_base.json'
        )
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(self.knowledge_base_path), exist_ok=True)
        
        # Initialize knowledge base
        self.knowledge_base = self._load_knowledge_base()
        logger.info(f"Initialized knowledge processor with knowledge base at: {self.knowledge_base_path}")
    
    def _load_knowledge_base(self) -> Dict[str, Any]:
        """Load the knowledge base from file.
        
        Returns:
            Dictionary containing the knowledge base
        """
        try:
            if os.path.exists(self.knowledge_base_path):
                with open(self.knowledge_base_path, 'r') as f:
                    knowledge_base = json.load(f)
                logger.info(f"Loaded knowledge base with {len(knowledge_base.get('items', []))} items")
                return knowledge_base
            else:
                # Create new knowledge base
                knowledge_base = {
                    "metadata": {
                        "created_at": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat(),
                        "version": "1.0"
                    },
                    "items": [],
                    "categories": {},
                    "documents": {}
                }
                self._save_knowledge_base(knowledge_base)
                logger.info("Created new knowledge base")
                return knowledge_base
        except Exception as e:
            logger.error(f"Error loading knowledge base: {str(e)}")
            # Return empty knowledge base
            return {
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                    "version": "1.0"
                },
                "items": [],
                "categories": {},
                "documents": {}
            }
    
    def _save_knowledge_base(self, knowledge_base: Dict[str, Any]) -> bool:
        """Save the knowledge base to file.
        
        Args:
            knowledge_base: Dictionary containing the knowledge base
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Update metadata
            knowledge_base["metadata"]["updated_at"] = datetime.now().isoformat()
            
            with open(self.knowledge_base_path, 'w') as f:
                json.dump(knowledge_base, f, indent=2)
            logger.info(f"Saved knowledge base with {len(knowledge_base.get('items', []))} items")
            return True
        except Exception as e:
            logger.error(f"Error saving knowledge base: {str(e)}")
            return False
    
    def add_knowledge_items(self, items: List[Dict[str, Any]], document_name: str) -> int:
        """Add knowledge items to the knowledge base.
        
        Args:
            items: List of knowledge items to add
            document_name: Name of the source document
            
        Returns:
            Number of items added
        """
        if not items:
            logger.warning(f"No knowledge items to add from document: {document_name}")
            return 0
        
        logger.info(f"Adding {len(items)} knowledge items from document: {document_name}")
        
        # Load the latest knowledge base
        knowledge_base = self._load_knowledge_base()
        
        # Add document to documents if not exists
        if document_name not in knowledge_base["documents"]:
            knowledge_base["documents"][document_name] = {
                "added_at": datetime.now().isoformat(),
                "item_count": 0
            }
        
        # Add items to knowledge base
        added_count = 0
        for item in items:
            # Add unique ID to item
            item_id = f"item_{len(knowledge_base['items']) + 1}"
            item["id"] = item_id
            item["added_at"] = datetime.now().isoformat()
            item["source"] = document_name
            
            # Add category to categories if not exists
            category = item.get("category", "uncategorized")
            if category not in knowledge_base["categories"]:
                knowledge_base["categories"][category] = {
                    "item_count": 0
                }
            
            # Add item to knowledge base
            knowledge_base["items"].append(item)
            
            # Update counts
            knowledge_base["documents"][document_name]["item_count"] += 1
            knowledge_base["categories"][category]["item_count"] += 1
            
            added_count += 1
        
        # Save knowledge base
        if self._save_knowledge_base(knowledge_base):
            logger.info(f"Successfully added {added_count} knowledge items")
            return added_count
        else:
            logger.error("Failed to save knowledge base")
            return 0
    
    def get_knowledge_items(
        self, 
        category: Optional[str] = None, 
        document_name: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get knowledge items from the knowledge base.
        
        Args:
            category: Optional category to filter by
            document_name: Optional document name to filter by
            limit: Optional maximum number of items to return
            
        Returns:
            List of knowledge items
        """
        knowledge_base = self._load_knowledge_base()
        items = knowledge_base.get("items", [])
        
        # Filter by category
        if category:
            items = [item for item in items if item.get("category") == category]
        
        # Filter by document name
        if document_name:
            items = [item for item in items if item.get("source") == document_name]
        
        # Limit number of items
        if limit and limit > 0:
            items = items[:limit]
        
        logger.info(f"Retrieved {len(items)} knowledge items")
        return items
    
    def get_rules_for_campaign_type(self, campaign_objective: str) -> List[Dict[str, Any]]:
        """Get knowledge items relevant to a specific campaign objective.
        
        Args:
            campaign_objective: Campaign objective (e.g., 'conversions', 'traffic', 'awareness')
            
        Returns:
            List of relevant knowledge items
        """
        logger.info(f"Getting rules for campaign objective: {campaign_objective}")
        
        # Get all knowledge items
        all_items = self.get_knowledge_items()
        
        # Filter items relevant to the campaign objective
        relevant_items = []
        for item in all_items:
            # Check if the item is relevant to the campaign objective
            # This is a simple implementation - in a real system, you would use more sophisticated matching
            rule = item.get("rule", "").lower()
            conditions = item.get("conditions", "").lower()
            
            if (
                campaign_objective.lower() in rule or 
                campaign_objective.lower() in conditions or
                "all campaigns" in rule.lower() or
                "all objectives" in rule.lower()
            ):
                relevant_items.append(item)
        
        logger.info(f"Found {len(relevant_items)} relevant rules for campaign objective: {campaign_objective}")
        return relevant_items
    
    def search_knowledge_base(self, query: str) -> List[Dict[str, Any]]:
        """Search the knowledge base for items matching the query.
        
        Args:
            query: Search query
            
        Returns:
            List of matching knowledge items
        """
        logger.info(f"Searching knowledge base for: {query}")
        
        # Get all knowledge items
        all_items = self.get_knowledge_items()
        
        # Filter items matching the query
        matching_items = []
        query_lower = query.lower()
        
        for item in all_items:
            # Check if the query matches any field in the item
            rule = item.get("rule", "").lower()
            category = item.get("category", "").lower()
            conditions = item.get("conditions", "").lower()
            outcome = item.get("outcome", "").lower()
            
            if (
                query_lower in rule or
                query_lower in category or
                query_lower in conditions or
                query_lower in outcome
            ):
                matching_items.append(item)
        
        logger.info(f"Found {len(matching_items)} items matching query: {query}")
        return matching_items
    
    def get_knowledge_base_summary(self) -> Dict[str, Any]:
        """Get a summary of the knowledge base.
        
        Returns:
            Dictionary containing summary information
        """
        knowledge_base = self._load_knowledge_base()
        
        summary = {
            "total_items": len(knowledge_base.get("items", [])),
            "categories": knowledge_base.get("categories", {}),
            "documents": knowledge_base.get("documents", {}),
            "metadata": knowledge_base.get("metadata", {})
        }
        
        logger.info(f"Generated knowledge base summary with {summary['total_items']} total items")
        return summary
    
    def delete_knowledge_item(self, item_id: str) -> bool:
        """Delete a knowledge item from the knowledge base.
        
        Args:
            item_id: ID of the item to delete
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Deleting knowledge item: {item_id}")
        
        # Load the latest knowledge base
        knowledge_base = self._load_knowledge_base()
        
        # Find the item
        items = knowledge_base.get("items", [])
        for i, item in enumerate(items):
            if item.get("id") == item_id:
                # Get item details for updating counts
                category = item.get("category", "uncategorized")
                document_name = item.get("source", "unknown")
                
                # Remove the item
                removed_item = items.pop(i)
                
                # Update counts
                if document_name in knowledge_base["documents"]:
                    knowledge_base["documents"][document_name]["item_count"] -= 1
                
                if category in knowledge_base["categories"]:
                    knowledge_base["categories"][category]["item_count"] -= 1
                
                # Save knowledge base
                if self._save_knowledge_base(knowledge_base):
                    logger.info(f"Successfully deleted knowledge item: {item_id}")
                    return True
                else:
                    logger.error(f"Failed to save knowledge base after deleting item: {item_id}")
                    return False
        
        logger.warning(f"Knowledge item not found: {item_id}")
        return False
    
    def update_knowledge_item(self, item_id: str, updated_data: Dict[str, Any]) -> bool:
        """Update a knowledge item in the knowledge base.
        
        Args:
            item_id: ID of the item to update
            updated_data: Dictionary containing updated data
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Updating knowledge item: {item_id}")
        
        # Load the latest knowledge base
        knowledge_base = self._load_knowledge_base()
        
        # Find the item
        items = knowledge_base.get("items", [])
        for i, item in enumerate(items):
            if item.get("id") == item_id:
                # Get original category for updating counts
                original_category = item.get("category", "uncategorized")
                
                # Update the item
                for key, value in updated_data.items():
                    # Don't update id, source, or added_at
                    if key not in ["id", "source", "added_at"]:
                        item[key] = value
                
                # Add updated_at timestamp
                item["updated_at"] = datetime.now().isoformat()
                
                # Update category counts if category changed
                new_category = item.get("category", "uncategorized")
                if new_category != original_category:
                    # Decrease count for original category
                    if original_category in knowledge_base["categories"]:
                        knowledge_base["categories"][original_category]["item_count"] -= 1
                    
                    # Add new category if not exists
                    if new_category not in knowledge_base["categories"]:
                        knowledge_base["categories"][new_category] = {
                            "item_count": 0
                        }
                    
                    # Increase count for new category
                    knowledge_base["categories"][new_category]["item_count"] += 1
                
                # Save knowledge base
                if self._save_knowledge_base(knowledge_base):
                    logger.info(f"Successfully updated knowledge item: {item_id}")
                    return True
                else:
                    logger.error(f"Failed to save knowledge base after updating item: {item_id}")
                    return False
        
        logger.warning(f"Knowledge item not found: {item_id}")
        return False
    
    def clear_knowledge_base(self) -> bool:
        """Clear all items from the knowledge base.
        
        Returns:
            True if successful, False otherwise
        """
        logger.warning("Clearing all items from knowledge base")
        
        # Create new empty knowledge base
        knowledge_base = {
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "version": "1.0"
            },
            "items": [],
            "categories": {},
            "documents": {}
        }
        
        # Save knowledge base
        if self._save_knowledge_base(knowledge_base):
            logger.info("Successfully cleared knowledge base")
            return True
        else:
            logger.error("Failed to clear knowledge base")
            return False
    
    def export_knowledge_base(self, export_path: Optional[str] = None) -> str:
        """Export the knowledge base to a file.
        
        Args:
            export_path: Path to export the knowledge base to. If None, will use default path.
            
        Returns:
            Path to the exported file
        """
        export_path = export_path or os.path.join(
            os.getcwd(), 'exports', f'knowledge_base_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        )
        
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(export_path), exist_ok=True)
        
        try:
            # Load the latest knowledge base
            knowledge_base = self._load_knowledge_base()
            
            # Add export metadata
            knowledge_base["export_metadata"] = {
                "exported_at": datetime.now().isoformat(),
                "item_count": len(knowledge_base.get("items", []))
            }
            
            # Export knowledge base
            with open(export_path, 'w') as f:
                json.dump(knowledge_base, f, indent=2)
            
            logger.info(f"Successfully exported knowledge base to: {export_path}")
            return export_path
        except Exception as e:
            logger.error(f"Error exporting knowledge base: {str(e)}")
            return ""
    
    def import_knowledge_base(self, import_path: str) -> bool:
        """Import a knowledge base from a file.
        
        Args:
            import_path: Path to the file to import
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Importing knowledge base from: {import_path}")
        
        try:
            # Check if file exists
            if not os.path.exists(import_path):
                logger.error(f"Import file not found: {import_path}")
                return False
            
            # Load the import file
            with open(import_path, 'r') as f:
                import_data = json.load(f)
            
            # Validate import data
            if "items" not in import_data:
                logger.error("Invalid import data: 'items' field not found")
                return False
            
            # Save imported knowledge base
            if self._save_knowledge_base(import_data):
                logger.info(f"Successfully imported knowledge base with {len(import_data.get('items', []))} items")
                return True
            else:
                logger.error("Failed to save imported knowledge base")
                return False
        except Exception as e:
            logger.error(f"Error importing knowledge base: {str(e)}")
            return False

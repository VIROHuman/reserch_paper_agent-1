"""
Author Name Particle Normalization

Handles name particles (von, de, van, di, etc.) correctly:
- Particles belong to the SURNAME, not the given name
- Prevents duplication of particles in given names
"""
import re
from typing import Tuple, List, Optional
from loguru import logger

# Common name particles (case-insensitive)
NAME_PARTICLES = {
    'von', 'van', 'de', 'der', 'den', 'des', 'du', 'da', 'di', 'del', 'della',
    'le', 'la', 'les', 'el', 'al', 'bin', 'ibn', 'af', 'av', 'zu', 'zur',
    'ter', 'ten', 'te', 'op', 'het', 'mc', 'mac', 'o', 'fitz'
}

# Patterns for detecting particles
PARTICLE_PATTERN = re.compile(
    r'\b(' + '|'.join(re.escape(p) for p in NAME_PARTICLES) + r')\b',
    re.IGNORECASE
)


def normalize_author_with_particles(full_name: str) -> Tuple[str, str]:
    """
    Normalize author name, correctly handling particles.
    
    Args:
        full_name: Full author name (e.g., "Thomas von Zglinicki")
        
    Returns:
        Tuple of (surname_with_particle, given_name_without_particle)
        Example: ("von Zglinicki", "Thomas")
    """
    if not full_name or not full_name.strip():
        return "", ""
    
    name_parts = full_name.strip().split()
    if not name_parts:
        return "", ""
    
    # Find particles in the name
    particles = []
    non_particle_parts = []
    
    for part in name_parts:
        if part.lower() in NAME_PARTICLES:
            particles.append(part)
        else:
            non_particle_parts.append(part)
    
    if not non_particle_parts:
        # All particles? Return as surname
        return full_name, ""
    
    # Surname is the last non-particle part, plus any particles before it
    # Given name is everything before the particles + last part
    if particles:
        # Find where particles start
        particle_start_idx = None
        for i, part in enumerate(name_parts):
            if part.lower() in NAME_PARTICLES:
                particle_start_idx = i
                break
        
        if particle_start_idx is not None:
            # Given name: everything before particles
            given_name = " ".join(name_parts[:particle_start_idx])
            # Surname: particles + last part(s)
            surname = " ".join(name_parts[particle_start_idx:])
            return surname, given_name
    
    # No particles found - standard case: last name is surname
    if len(non_particle_parts) == 1:
        return non_particle_parts[0], ""
    
    surname = non_particle_parts[-1]
    given_name = " ".join(non_particle_parts[:-1])
    return surname, given_name


def normalize_family_name(family_name: str, given_name: str = "") -> Tuple[str, str]:
    """
    Normalize family and given names, ensuring particles stay with surname.
    
    This function handles cases where particles might have been incorrectly
    placed in the given name field.
    
    Args:
        family_name: Family name (may or may not contain particles)
        given_name: Given name (may incorrectly contain particles)
        
    Returns:
        Tuple of (normalized_family_name, normalized_given_name)
    """
    if not family_name:
        return "", given_name or ""
    
    family_name = family_name.strip()
    given_name = given_name.strip() if given_name else ""
    
    # Check if given name contains particles that should be in family name
    if given_name:
        given_parts = given_name.split()
        family_parts = family_name.split()
        
        # Check if last part of given name is a particle
        if given_parts and given_parts[-1].lower() in NAME_PARTICLES:
            # Move particle to family name
            particle = given_parts.pop()
            given_name = " ".join(given_parts)
            family_name = f"{particle} {family_name}".strip()
            logger.debug(f"Moved particle '{particle}' from given to family name")
        
        # Check if given name contains particles in the middle
        # Pattern: "Thomas von" -> should be "Thomas" (family: "von ...")
        for i, part in enumerate(given_parts):
            if part.lower() in NAME_PARTICLES:
                # Found particle in given name - move it and everything after to family name
                particles_and_after = " ".join(given_parts[i:])
                given_name = " ".join(given_parts[:i])
                family_name = f"{particles_and_after} {family_name}".strip()
                logger.debug(f"Moved particle '{particles_and_after}' from given to family name")
                break
    
    return family_name, given_name


def normalize_author_list(
    family_names: List[str],
    given_names: List[str]
) -> Tuple[List[str], List[str]]:
    """
    Normalize a list of authors, ensuring particles are correctly placed.
    
    Args:
        family_names: List of family names
        given_names: List of given names (aligned with family_names)
        
    Returns:
        Tuple of (normalized_family_names, normalized_given_names)
    """
    normalized_family = []
    normalized_given = []
    
    max_len = max(len(family_names), len(given_names))
    
    for i in range(max_len):
        family = family_names[i] if i < len(family_names) else ""
        given = given_names[i] if i < len(given_names) else ""
        
        norm_family, norm_given = normalize_family_name(family, given)
        normalized_family.append(norm_family)
        normalized_given.append(norm_given)
    
    return normalized_family, normalized_given


